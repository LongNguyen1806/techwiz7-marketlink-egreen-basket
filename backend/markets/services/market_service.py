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
from accounts.models import FarmerProfile, FarmerStatus
from accounts.services.farmer_status_service import reinstate_farmer, suspend_farmer
from marketlink_core.history import save_with_history
from markets.models import FarmerMarket, Market, MarketOperatingDay, PickupSlot
from notifications.models import NotificationType
from notifications.services import notify
from orders.models import OPEN_STATUSES, ActorRole, ChangeReason, Order, OrderStatus
from orders.services.fsm import transition_order

SCHEDULE_FIELDS = ("operating_days", "open_time", "close_time")

# Stamped on every pickup slot a closure switches off and on every stall it suspends, so
# reopening can tell those apart from ones that were already off for a different reason.
CLOSURE_REASON = "Market #{market_id} closed by Admin (AD-17)"
REOPEN_REASON = "Market #{market_id} reopened by Admin (AD-17)"

# What the stall reads on its own profile. The line above is a marker for the machine; this
# is the sentence a person sees next to the suspension.
SUSPENSION_TEXT = "{market_name} has closed. The stall is suspended until it reopens."


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


# Edits the people at a market have to hear about. A new description or photo is not news.
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
    # Open orders whose pickup no longer falls inside the new days and hours.
    order_ids_to_cancel: list[int] = field(default_factory=list)
    slot_ids_to_disable: list[int] = field(default_factory=list)
    # recipient user id -> orders of theirs this edit cancels (0 = told, nothing cancelled)
    customers: dict[int, int] = field(default_factory=dict)
    farmers: dict[int, int] = field(default_factory=dict)
    # farmer user id -> pickup slots of theirs this edit switches off
    slots_per_farmer: dict[int, int] = field(default_factory=dict)

    def summary(self) -> dict[str, Any]:
        return {
            "changed_fields": self.changed_fields,
            "location_changed": self.location_changed,
            "schedule_changed": self.schedule_changed,
            "orders_to_cancel": len(self.order_ids_to_cancel),
            "slots_to_disable": len(self.slot_ids_to_disable),
            "customers_to_notify": len(self.customers),
            "stalls_to_notify": len(self.farmers),
        }


def _current_days(market: Market) -> set[int]:
    return set(
        MarketOperatingDay.objects.filter(market=market).values_list("day_of_week", flat=True)
    )


def _changed_fields(market: Market, validated: dict[str, Any]) -> list[str]:
    # The form sends every field on each save, so "sent" is not "changed": compare values.
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

        # Only pickups still ahead. One whose time has already come went ahead under the old
        # schedule; the expiry sweep and the stall close those out as usual.
        upcoming = Order.objects.filter(
            market=market, status__in=OPEN_STATUSES, pickup_start_at__gt=timezone.now()
        ).order_by("id")
        for order in upcoming:
            start = timezone.localtime(order.pickup_start_at)
            end = timezone.localtime(order.pickup_end_at)
            if _outside(days, open_time, close_time,
                        day=order.pickup_date.isoweekday(), start=start.time(), end=end.time()):
                impact.order_ids_to_cancel.append(order.pk)
                impact.customers[order.customer_id] = impact.customers.get(order.customer_id, 0) + 1
                impact.farmers[order.farmer_id] = impact.farmers.get(order.farmer_id, 0) + 1
        for farmer_id in impact.slots_per_farmer:
            impact.farmers.setdefault(farmer_id, 0)

    if impact.location_changed:
        # Everyone who is due to come here has to know where "here" is now.
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

    for customer_id, cancelled in sorted(impact.customers.items()):
        notify(
            recipient=users[customer_id],
            event_type=NotificationType.MARKET_UPDATED,
            context={
                "market_name": market.name,
                "changes": changes,
                "order_note": (
                    f"{cancelled} of your orders there no longer fit the new schedule and "
                    "were cancelled."
                    if cancelled
                    else "Your orders there still stand."
                ),
                "target_url": "/customer/orders",
            },
        )
    for farmer_id, cancelled in sorted(impact.farmers.items()):
        slots = impact.slots_per_farmer.get(farmer_id, 0)
        notify(
            recipient=users[farmer_id],
            event_type=NotificationType.MARKET_UPDATED,
            context={
                "market_name": market.name,
                "changes": changes,
                "order_note": (
                    f"{cancelled} of your orders there no longer fit and were cancelled; "
                    "their stock is back in your listings."
                    if cancelled
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


# D-022 / AD-16. Moving a market or changing when it runs reaches the people due there:
# - name, address, map position: everyone with an open order and every stall gets one notice;
# - days or hours: slots outside them switch off, and open orders whose pickup falls outside
#   them are declined (stock back) - but only once the admin has seen the count and confirmed.
# Each person gets a single notice that carries every change, never one per order.
@transaction.atomic
def update_market(
    *, market_id: int, validated: dict[str, Any], actor=None, confirm_cancel: bool = False
) -> tuple[Market, MarketEditImpact]:
    # Lock order fixed by §5: markets, then pickup_slots by id, to stay deadlock-free.
    market = Market.objects.select_for_update().get(pk=market_id)
    impact = preview_market_update(market=market, validated=validated)
    if impact.order_ids_to_cancel and not confirm_cancel:
        raise UnprocessableEntityError(
            f"This change cancels {len(impact.order_ids_to_cancel)} open orders. "
            "Confirm to go ahead.",
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
    # Row by row, never QuerySet.update(): the audit trail of pickup_slots has to record every
    # slot the admin switched off, and update() writes no history row (v1.8, AD-16).
    for slot in (
        PickupSlot.objects.filter(pk__in=impact.slot_ids_to_disable)
        .order_by("id")
        .select_for_update()
    ):
        slot.is_active = False
        save_with_history(slot, update_fields=["is_active", "updated_at"], reason=marker)

    # A pending change request dies with the order it belonged to (§5.4 step 4).
    for order in (
        Order.objects.filter(pk__in=impact.order_ids_to_cancel)
        .exclude(pending_change=None)
        .order_by("id")
    ):
        order.pending_change = None
        save_with_history(
            order, update_fields=["pending_change", "updated_at"], reason=marker, user=actor
        )
    for order_id in impact.order_ids_to_cancel:
        transition_order(
            order_id=order_id,
            to_status=OrderStatus.DECLINED,
            actor=actor,
            actor_role=ActorRole.ADMIN,
            admin_change_reason=ChangeReason.MARKET_SCHEDULE_CHANGED_BY_ADMIN,
            # The shopper hears it once, in the market notice below.
            notify_customer=False,
        )

    # notify() writes its row in this transaction and defers delivery to on_commit, so a
    # rollback leaves no notification behind and nobody is told before the change lands.
    if impact.customers or impact.farmers:
        _notify_update(market=market, old_name=old_name, impact=impact)
    return market, impact


# Closing a market used to be refused while orders were open. It now carries them out instead:
# every open order at the market is declined (stock goes back), the stalls' pickup slots there
# are switched off, and - since a stall trades at exactly one market - the stalls are suspended
# until it reopens.
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

    # Ordered by id so this cannot deadlock against a farmer or customer touching the same rows.
    order_ids = list(
        Order.objects.filter(market_id=market_id, status__in=OPEN_STATUSES)
        .order_by("id")
        .values_list("id", flat=True)
    )
    # A pending change request dies with the order it belonged to (§5.4 step 4). Saved one by
    # one: QuerySet.update() writes no history row, and the order trail has to show this.
    for order in Order.objects.filter(pk__in=order_ids).exclude(pending_change=None).order_by("id"):
        order.pending_change = None
        save_with_history(
            order,
            update_fields=["pending_change", "updated_at"],
            reason=CLOSURE_REASON.format(market_id=market_id),
            user=actor,
        )

    # Counted per recipient before the transitions run, because afterwards none of these
    # orders is open any more.
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
            # Without this the shopper is told the stall was suspended by an administrator,
            # which is not what happened and, for a stall trading normally, is a slur.
            admin_change_reason=ChangeReason.MARKET_CLOSED_BY_ADMIN,
            # Each shopper gets one MARKET_CLOSED notice below, not one per order.
            notify_customer=False,
        )

    # Row by row, never QuerySet.update(): the audit trail has to record each slot (v1.8).
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

    # A stall trades at exactly one market, so closing that market leaves it with nowhere to
    # sell: it is suspended until the market reopens, and trading anywhere else means
    # registering again. Done after the orders, not before - suspend_farmer would otherwise
    # decline those same orders and stamp them with the wrong reason.
    suspended = _suspend_stalls(market=market, actor=actor)

    _notify_closure(market=market, reason=reason, per_customer=orders_per_customer,
                    per_farmer=orders_per_farmer, market_id=market_id,
                    farmer_message=farmer_message, suspended=suspended)
    return market, len(order_ids)


def _suspend_stalls(*, market: Market, actor) -> set[int]:
    """Suspend every approved stall at this market. Returns whose accounts changed.

    Pending and rejected stalls are left alone: the state machine only admits
    APPROVED -> SUSPENDED, and forcing an unapproved profile through it would raise and take
    the whole closure down with it.
    """
    farmer_ids = list(
        FarmerProfile.objects.filter(
            farmer_markets__market_id=market.pk, status=FarmerStatus.APPROVED
        )
        .order_by("user_id")
        .values_list("user_id", flat=True)
    )
    for farmer_id in farmer_ids:
        suspend_farmer(
            farmer_id=farmer_id,
            reason=SUSPENSION_TEXT.format(market_name=market.name),
            actor=actor,
            history_reason=CLOSURE_REASON.format(market_id=market.pk),
            # The market-closed notice below says this too; two messages about one event
            # read as two separate problems.
            send_notification=False,
        )
    return set(farmer_ids)


def _notify_closure(*, market: Market, reason: str, per_customer: dict[int, int],
                    per_farmer: dict[int, int], market_id: int,
                    farmer_message: str = "", suspended: set[int] | None = None) -> None:
    """Tell everyone who had something at the market, with the reason the admin typed."""
    # Farmers with a stall here but no open order still need to know the market has gone.
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
    suspended = suspended or set()
    for recipient_id, count in sorted(per_farmer.items()):
        notify(
            recipient=users[recipient_id],
            event_type=NotificationType.MARKET_CLOSED,
            # Only the stalls get the admin's note; it is written for them. The suspension
            # rides along in the same message instead of arriving as a second one.
            context={"market_name": market.name, "order_count": count, "reason": reason,
                     "target_url": "/farmer/markets", "admin_message": farmer_message,
                     "stall_note": (
                         "Your stall is suspended until this market reopens."
                         if recipient_id in suspended
                         else ""
                     )},
        )


@transaction.atomic
def activate_market(*, market_id: int) -> tuple[Market, int]:
    market = Market.objects.select_for_update().get(pk=market_id)
    market.is_active = True
    market.save(update_fields=["is_active", "updated_at"])

    reason = CLOSURE_REASON.format(market_id=market_id)
    # Stalls come back before their slots do, so a reopened market is never briefly showing
    # collection times for a stall that is still suspended.
    _reinstate_stalls(market_id=market_id, marker=reason)

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
        # Only the ones this closure switched off. A slot the farmer turned off themselves,
        # or one AD-16 disabled for falling outside the hours, stays off.
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


def _reinstate_stalls(*, market_id: int, marker: str) -> set[int]:
    """Put back exactly the stalls this closure suspended.

    Matched by the marker the closure stamped on the profile history, the same way the slots
    above are matched. A stall suspended for its own reasons, before or during the closure,
    keeps its suspension: reopening a market is not an amnesty.
    """
    pk_field = FarmerProfile._meta.pk.attname
    reinstated: set[int] = set()
    farmer_ids = list(
        FarmerProfile.objects.filter(
            farmer_markets__market_id=market_id, status=FarmerStatus.SUSPENDED
        )
        .order_by("user_id")
        .values_list("user_id", flat=True)
    )
    for farmer_id in farmer_ids:
        latest = (
            FarmerProfile.history.filter(**{pk_field: farmer_id})
            .order_by("history_date", "history_id")
            .last()
        )
        if latest is None or latest.history_change_reason != marker:
            continue
        reinstate_farmer(
            farmer_id=farmer_id,
            actor=None,
            history_reason=REOPEN_REASON.format(market_id=market_id),
            # The stall gets told its account is approved again, which is the useful half;
            # there is no separate "market reopened" notice to collide with.
        )
        reinstated.add(farmer_id)
    return reinstated
