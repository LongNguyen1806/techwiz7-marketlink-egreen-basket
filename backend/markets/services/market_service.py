from dataclasses import dataclass, field
from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from marketlink_core.exceptions import (
    BusinessValidationError,
    ErrorCode,
    UnprocessableEntityError,
)
from marketlink_core.history import save_with_history
from markets.models import FarmerMarket, Market, MarketOperatingDay, PickupSlot
from notifications.models import NotificationType
from notifications.services import notify
from marketlink_core.context import get_request_id
from orders.models import (
    OPEN_STATUSES,
    ActorRole,
    ChangeReason,
    Order,
    OrderStatus,
    OrderStatusHistory,
)
from orders.services.fsm import transition_order

SCHEDULE_FIELDS = ("operating_days", "open_time", "close_time")

CLOSURE_REASON = "Market #{market_id} closed by Admin (AD-17)"
REOPEN_REASON = "Market #{market_id} reopened by Admin (AD-17)"


def _replace_operating_days(*, market: Market, days: list[int]) -> None:
    MarketOperatingDay.objects.filter(market=market).delete()
    MarketOperatingDay.objects.bulk_create(
        [MarketOperatingDay(market=market, day_of_week=day) for day in sorted(set(days))]
    )


@transaction.atomic
def create_market(*, validated: dict[str, Any]) -> Market:
    days = validated.pop("operating_days")
    market = Market.objects.create(**validated)
    _replace_operating_days(market=market, days=days)
    return market


LOCATION_FIELDS = ("name", "address", "latitude", "longitude")
SCHEDULE_CHANGE_MARKER = "Market #{market_id} schedule changed by Admin (AD-16)"
DAY_LABELS = {1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun"}


@dataclass
class MarketEditImpact:
    """What saving an edit would do, worked out before anything is written.

    The same answer feeds the preview the admin confirms and the save itself, so the numbers
    in the dialog are the numbers that happen.
    """

    changed_fields: list[str]
    location_changed: bool
    schedule_changed: bool
    order_ids_to_reschedule: list[int] = field(default_factory=list)
    slot_ids_to_disable: list[int] = field(default_factory=list)
    customers: dict[int, int] = field(default_factory=dict)
    farmers: dict[int, int] = field(default_factory=dict)
    slots_per_farmer: dict[int, int] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        return {
            "changed_fields": self.changed_fields,
            "location_changed": self.location_changed,
            "schedule_changed": self.schedule_changed,
            "orders_to_reschedule": len(self.order_ids_to_reschedule),
            "slots_to_disable": len(self.slot_ids_to_disable),
            "customers_to_notify": len(self.customers),
            "stalls_to_notify": len(self.farmers),
        }


def _current_days(market: Market) -> set[int]:
    return set(
        MarketOperatingDay.objects.filter(market=market).values_list("day_of_week", flat=True)
    )


def _changed_fields(market: Market, validated: dict[str, Any]) -> list[str]:
    changed = []
    for name, value in validated.items():
        if name == "operating_days":
            if set(value) != _current_days(market):
                changed.append(name)
        elif name == "image":
            changed.append(name)
        elif getattr(market, name) != value:
            changed.append(name)
    return sorted(changed)


def _outside(days: set[int], open_time, close_time, *, day: int, start, end) -> bool:
    return day not in days or start < open_time or end > close_time


def preview_market_update(*, market: Market, validated: dict[str, Any]) -> MarketEditImpact:
    changed = _changed_fields(market, validated)
    impact = MarketEditImpact(
        changed_fields=changed,
        location_changed=any(name in changed for name in LOCATION_FIELDS),
        schedule_changed=any(name in changed for name in SCHEDULE_FIELDS),
    )

    if impact.schedule_changed:
        days = set(validated.get("operating_days") or _current_days(market))
        open_time = validated.get("open_time", market.open_time)
        close_time = validated.get("close_time", market.close_time)

        for slot in (
            PickupSlot.objects.filter(farmer_market__market=market, is_active=True)
            .select_related("farmer_market")
            .order_by("id")
        ):
            if _outside(days, open_time, close_time,
                        day=slot.day_of_week, start=slot.start_time, end=slot.end_time):
                impact.slot_ids_to_disable.append(slot.pk)
                farmer_id = slot.farmer_market.farmer_id
                impact.slots_per_farmer[farmer_id] = impact.slots_per_farmer.get(farmer_id, 0) + 1

        upcoming = Order.objects.filter(
            market=market,
            status__in=OPEN_STATUSES,
            pickup_start_at__gt=timezone.now(),
            reschedule_requested_at__isnull=True,
        ).order_by("id")
        for order in upcoming:
            start = timezone.localtime(order.pickup_start_at)
            end = timezone.localtime(order.pickup_end_at)
            if _outside(days, open_time, close_time,
                        day=order.pickup_date.isoweekday(), start=start.time(), end=end.time()):
                impact.order_ids_to_reschedule.append(order.pk)
                impact.customers[order.customer_id] = impact.customers.get(order.customer_id, 0) + 1
                impact.farmers[order.farmer_id] = impact.farmers.get(order.farmer_id, 0) + 1
        for farmer_id in impact.slots_per_farmer:
            impact.farmers.setdefault(farmer_id, 0)

    if impact.location_changed:
        for customer_id in (
            Order.objects.filter(market=market, status__in=OPEN_STATUSES)
            .values_list("customer_id", flat=True)
            .distinct()
        ):
            impact.customers.setdefault(customer_id, 0)
        for farmer_id in FarmerMarket.objects.filter(market=market).values_list(
            "farmer_id", flat=True
        ):
            impact.farmers.setdefault(farmer_id, 0)

    return impact


def _change_lines(*, old_name: str, market: Market, impact: MarketEditImpact) -> str:
    lines = []
    if "name" in impact.changed_fields:
        lines.append(f"It was called {old_name} and is now {market.name}.")
    if "address" in impact.changed_fields:
        lines.append(f"The address is now {market.address}.")
    elif "latitude" in impact.changed_fields or "longitude" in impact.changed_fields:
        lines.append("Its place on the map has been corrected.")
    if impact.schedule_changed:
        days = ", ".join(DAY_LABELS[day] for day in sorted(_current_days(market)))
        lines.append(
            f"It now opens {days}, {market.open_time:%H:%M}-{market.close_time:%H:%M}."
        )
    return " ".join(lines)


def _notify_update(*, market: Market, old_name: str, impact: MarketEditImpact) -> None:
    changes = _change_lines(old_name=old_name, market=market, impact=impact)
    users = get_user_model().objects.in_bulk(sorted(set(impact.customers) | set(impact.farmers)))

    for customer_id, moved in sorted(impact.customers.items()):
        notify(
            recipient=users[customer_id],
            event_type=NotificationType.MARKET_UPDATED,
            context={
                "market_name": market.name,
                "changes": changes,
                "order_note": (
                    f"{moved} of your orders there no longer fit the new schedule. Please "
                    "choose a new pickup time, or cancel; if nothing is chosen by the old "
                    "pickup time, the order is cancelled."
                    if moved
                    else "Your orders there still stand."
                ),
                "target_url": "/customer/orders",
            },
        )
    for farmer_id, moved in sorted(impact.farmers.items()):
        slots = impact.slots_per_farmer.get(farmer_id, 0)
        notify(
            recipient=users[farmer_id],
            event_type=NotificationType.MARKET_UPDATED,
            context={
                "market_name": market.name,
                "changes": changes,
                "order_note": (
                    f"{moved} of your orders there no longer fit; the shoppers have been "
                    "asked to choose a new pickup time."
                    if moved
                    else ""
                ),
                "slot_note": (
                    f"{slots} of your pickup slots fall outside the new schedule and were "
                    "turned off. Please review them."
                    if slots
                    else ""
                ),
                "target_url": "/farmer/markets",
            },
        )


@transaction.atomic
def update_market(
    *, market_id: int, validated: dict[str, Any], actor=None, confirm_affected: bool = False
) -> tuple[Market, MarketEditImpact]:
    market = Market.objects.select_for_update().get(pk=market_id)
    impact = preview_market_update(market=market, validated=validated)
    if impact.order_ids_to_reschedule and not confirm_affected:
        raise UnprocessableEntityError(
            f"{len(impact.order_ids_to_reschedule)} open orders no longer fit this "
            "schedule and will need a new pickup time. Confirm to go ahead.",
            code=ErrorCode.FAILED_PRECONDITION,
            data=impact.summary(),
        )

    old_name = market.name
    days = validated.pop("operating_days", None)
    for name, value in validated.items():
        setattr(market, name, value)
    market.save()
    if days is not None:
        _replace_operating_days(market=market, days=days)

    marker = SCHEDULE_CHANGE_MARKER.format(market_id=market_id)
    for slot in (
        PickupSlot.objects.filter(pk__in=impact.slot_ids_to_disable)
        .order_by("id")
        .select_for_update()
    ):
        slot.is_active = False
        save_with_history(slot, update_fields=["is_active", "updated_at"], reason=marker)

    now = timezone.now()
    for order in (
        Order.objects.filter(pk__in=impact.order_ids_to_reschedule)
        .order_by("id")
        .select_for_update(of=("self",))
    ):
        order.reschedule_requested_at = now
        order.pending_change = None
        order.version += 1
        save_with_history(
            order,
            update_fields=["reschedule_requested_at", "pending_change", "version", "updated_at"],
            reason=marker,
            user=actor,
        )
        OrderStatusHistory.objects.create(
            order=order,
            from_status=order.status,
            to_status=order.status,
            transition=None,
            actor=actor,
            actor_role=ActorRole.ADMIN,
            change_reason="The market changed its schedule; a new pickup time is needed.",
            request_id=get_request_id(),
        )

    if impact.customers or impact.farmers:
        _notify_update(market=market, old_name=old_name, impact=impact)
    return market, impact


@transaction.atomic
def deactivate_market(
    *, market_id: int, reason: str, actor, farmer_message: str = ""
) -> tuple[Market, int]:
    market = Market.objects.select_for_update().get(pk=market_id)
    if not market.is_active:
        raise BusinessValidationError(
            "This market is already closed.",
            code=ErrorCode.INVALID_STATUS_TRANSITION,
        )

    market.is_active = False
    market.save(update_fields=["is_active", "updated_at"])

    order_ids = list(
        Order.objects.filter(market_id=market_id, status__in=OPEN_STATUSES)
        .order_by("id")
        .values_list("id", flat=True)
    )
    for order in Order.objects.filter(pk__in=order_ids).exclude(pending_change=None).order_by("id"):
        order.pending_change = None
        save_with_history(
            order,
            update_fields=["pending_change", "updated_at"],
            reason=CLOSURE_REASON.format(market_id=market_id),
            user=actor,
        )

    orders_per_customer: dict[int, int] = {}
    orders_per_farmer: dict[int, int] = {}
    for customer_id, farmer_id in Order.objects.filter(pk__in=order_ids).values_list(
        "customer_id", "farmer_id"
    ):
        orders_per_customer[customer_id] = orders_per_customer.get(customer_id, 0) + 1
        orders_per_farmer[farmer_id] = orders_per_farmer.get(farmer_id, 0) + 1

    for order_id in order_ids:
        transition_order(
            order_id=order_id,
            to_status=OrderStatus.DECLINED,
            actor=actor,
            actor_role=ActorRole.ADMIN,
            admin_change_reason=ChangeReason.MARKET_CLOSED_BY_ADMIN,
            notify_customer=False,
        )

    slots = list(
        PickupSlot.objects.filter(farmer_market__market_id=market_id, is_active=True)
        .order_by("id")
        .select_for_update(of=("self",))
    )
    for slot in slots:
        slot.is_active = False
        save_with_history(
            slot,
            update_fields=["is_active", "updated_at"],
            reason=CLOSURE_REASON.format(market_id=market_id),
        )

    _notify_closure(market=market, reason=reason, per_customer=orders_per_customer,
                    per_farmer=orders_per_farmer, market_id=market_id,
                    farmer_message=farmer_message)
    return market, len(order_ids)


def _notify_closure(*, market: Market, reason: str, per_customer: dict[int, int],
                    per_farmer: dict[int, int], market_id: int,
                    farmer_message: str = "") -> None:
    """Tell everyone who had something at the market, with the reason the admin typed."""
    silent_farmers = set(
        FarmerMarket.objects.filter(market_id=market_id).values_list("farmer_id", flat=True)
    ) - set(per_farmer)
    for farmer_id in silent_farmers:
        per_farmer[farmer_id] = 0

    users = get_user_model().objects.in_bulk(sorted(set(per_customer) | set(per_farmer)))
    for recipient_id, count in sorted(per_customer.items()):
        notify(
            recipient=users[recipient_id],
            event_type=NotificationType.MARKET_CLOSED,
            context={"market_name": market.name, "order_count": count, "reason": reason,
                     "target_url": "/customer/orders", "admin_message": ""},
        )
    for recipient_id, count in sorted(per_farmer.items()):
        notify(
            recipient=users[recipient_id],
            event_type=NotificationType.MARKET_CLOSED,
            context={"market_name": market.name, "order_count": count, "reason": reason,
                     "target_url": "/farmer/markets", "admin_message": farmer_message},
        )


@transaction.atomic
def activate_market(*, market_id: int) -> tuple[Market, int]:
    market = Market.objects.select_for_update().get(pk=market_id)
    market.is_active = True
    market.save(update_fields=["is_active", "updated_at"])

    reason = CLOSURE_REASON.format(market_id=market_id)

    slots = list(
        PickupSlot.objects.filter(farmer_market__market_id=market_id, is_active=False)
        .order_by("id")
        .select_for_update(of=("self",))
    )
    restored = 0
    for slot in slots:
        latest = (
            PickupSlot.history.filter(id=slot.pk)
            .order_by("history_date", "history_id")
            .last()
        )
        if latest is None or latest.history_change_reason != reason:
            continue
        slot.is_active = True
        save_with_history(
            slot,
            update_fields=["is_active", "updated_at"],
            reason=REOPEN_REASON.format(market_id=market_id),
        )
        restored += 1

    return market, restored
