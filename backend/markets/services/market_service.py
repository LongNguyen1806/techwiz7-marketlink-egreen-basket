from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction

from marketlink_core.exceptions import ErrorCode, UnprocessableEntityError
from marketlink_core.history import save_with_history
from markets.models import FarmerMarket, Market, MarketOperatingDay, PickupSlot
from notifications.models import NotificationType
from notifications.services import notify
from orders.models import OPEN_STATUSES, ActorRole, ChangeReason, Order, OrderStatus
from orders.services.fsm import transition_order

SCHEDULE_FIELDS = ("operating_days", "open_time", "close_time")


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


# D-022: slots outside the new schedule switch off; placed orders keep their snapshot (D-007).
@transaction.atomic
def update_market(*, market_id: int, validated: dict[str, Any]) -> tuple[Market, int]:
    # Lock order fixed by §5: markets, then pickup_slots by id, to stay deadlock-free.
    market = Market.objects.select_for_update().get(pk=market_id)
    reschedules = any(field in validated for field in SCHEDULE_FIELDS)
    days = validated.pop("operating_days", None)

    for field, value in validated.items():
        setattr(market, field, value)
    market.save()

    if days is not None:
        _replace_operating_days(market=market, days=days)

    if not reschedules:
        return market, 0

    current_days = set(
        MarketOperatingDay.objects.filter(market=market).values_list("day_of_week", flat=True)
    )
    # Evaluated immediately so the lock is actually taken; of=("self",) keeps the join
    # tables out of the lock.
    slots = list(
        PickupSlot.objects.filter(farmer_market__market_id=market_id, is_active=True)
        .select_related("farmer_market")
        .order_by("id")
        .select_for_update(of=("self",))
    )
    outside = [
        slot
        for slot in slots
        if slot.day_of_week not in current_days
        or slot.start_time < market.open_time
        or slot.end_time > market.close_time
    ]
    if not outside:
        return market, 0

    # Row by row, never QuerySet.update(): the audit trail of pickup_slots has to record every
    # slot the admin switched off, and update() writes no history row (v1.8, AD-16).
    for slot in outside:
        slot.is_active = False
        save_with_history(
            slot,
            update_fields=["is_active", "updated_at"],
            reason=f"Market #{market_id} schedule changed by Admin (AD-16)",
        )

    slots_per_farmer: dict[int, int] = {}
    for slot in outside:
        farmer_id = slot.farmer_market.farmer_id
        slots_per_farmer[farmer_id] = slots_per_farmer.get(farmer_id, 0) + 1

    # farmer_profiles is keyed by user_id, so the farmer ids are already user ids.
    recipients = get_user_model().objects.in_bulk(sorted(slots_per_farmer))

    # notify() writes its row in this transaction and defers delivery to on_commit, so a
    # rollback leaves no notification behind and nobody is told before the change lands.
    for farmer_id, slot_count in sorted(slots_per_farmer.items()):
        notify(
            recipient=recipients[farmer_id],
            event_type=NotificationType.MARKET_SCHEDULE_CHANGED,
            context={"market_name": market.name, "slot_count": slot_count},
        )

    return market, len(outside)


# Closing a market used to be refused while orders were open. It now carries them out instead:
# every open order at the market is declined (stock goes back), and the stalls' pickup slots
# there are switched off. The stalls themselves are NOT suspended - a farmer may sell at several
# markets, and closing one of them is no fault of theirs.
@transaction.atomic
def deactivate_market(*, market_id: int, reason: str, actor) -> tuple[Market, int]:
    market = Market.objects.select_for_update().get(pk=market_id)
    if not market.is_active:
        raise UnprocessableEntityError(
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
    # A pending change request dies with the order it belonged to (§5.4 step 4).
    Order.objects.filter(pk__in=order_ids).exclude(pending_change=None).update(pending_change=None)

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
            # The order history says the market closed, not that the stall was suspended.
            admin_reason=ChangeReason.MARKET_CLOSED_BY_ADMIN,
            # Each customer gets one MARKET_CLOSED below instead of an ORDER_DECLINED per order.
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
            reason=f"Market #{market_id} closed by Admin (AD-17)",
        )

    _notify_closure(market=market, reason=reason, per_customer=orders_per_customer,
                    per_farmer=orders_per_farmer, market_id=market_id)
    return market, len(order_ids)


def _notify_closure(*, market: Market, reason: str, per_customer: dict[int, int],
                    per_farmer: dict[int, int], market_id: int) -> None:
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
                     "target_url": "/customer/orders"},
        )
    for recipient_id, count in sorted(per_farmer.items()):
        notify(
            recipient=users[recipient_id],
            event_type=NotificationType.MARKET_CLOSED,
            context={"market_name": market.name, "order_count": count, "reason": reason,
                     "target_url": "/farmer/markets"},
        )


@transaction.atomic
def activate_market(*, market_id: int) -> Market:
    market = Market.objects.select_for_update().get(pk=market_id)
    market.is_active = True
    market.save(update_fields=["is_active", "updated_at"])
    return market
