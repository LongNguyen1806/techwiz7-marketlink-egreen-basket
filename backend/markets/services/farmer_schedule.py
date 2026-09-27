"""F3: the farmer's markets, pickup slots and time off (FA-05 → FA-10, FA-32, FA-33).

Lock order (§5.2, v1.8): farmer_profiles -> farmer_markets -> pickup_slots, then orders are only
counted. Locking the profile first serializes every schedule change of one farmer, so a slot can
never be created on a weekday that FA-03 is removing at the same moment.
"""

from datetime import date, time
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.models import FarmerProfile
from marketlink_core.exceptions import (
    BusinessValidationError,
    ErrorCode,
    ResourceNotFoundError,
    UnprocessableEntityError,
)
from marketlink_core.history import delete_with_history
from markets.models import FarmerClosure, FarmerMarket, Market, MarketOperatingDay, PickupSlot
from orders.models import OPEN_STATUSES, Order
from orders.services.expiry import expire_overdue_orders
from orders.services.fsm import run_with_retry_if_top_level

INVALID_INPUT = "Invalid input. Please check the highlighted fields."


def _invalid(errors: dict[str, list[str]]) -> BusinessValidationError:
    return BusinessValidationError(INVALID_INPUT, errors=errors)


def _lock_profile(farmer_id: int) -> FarmerProfile:
    return FarmerProfile.objects.select_for_update(of=("self",)).get(pk=farmer_id)


def _lock_farmer_market(farmer_id: int, farmer_market_id: int) -> FarmerMarket:
    farmer_market = (
        FarmerMarket.objects.select_for_update(of=("self",))
        .select_related("market")
        .filter(pk=farmer_market_id, farmer_id=farmer_id)
        .first()
    )
    if farmer_market is None:
        raise ResourceNotFoundError("Market not found in your list.", code=ErrorCode.NOT_FOUND)
    return farmer_market


def _open_order_ids(**filters: Any) -> list[int]:
    return list(
        Order.objects.filter(status__in=OPEN_STATUSES, **filters).order_by("id").values_list("id", flat=True)
    )


# --- Markets (FA-05, FA-06, FA-07) ---


def join_market(*, farmer_id: int, market_id: int, stall_label: str) -> FarmerMarket:
    """FA-05: join an active market with a stall label (D-026)."""

    def _execute() -> FarmerMarket:
        with transaction.atomic():
            _lock_profile(farmer_id)
            market = Market.objects.filter(pk=market_id).first()
            if market is None or not market.is_active:
                raise _invalid({"market_id": ["This market is not available."]})
            if FarmerMarket.objects.filter(farmer_id=farmer_id, market_id=market_id).exists():
                raise _invalid({"market_id": ["You already sell at this market."]})
            return FarmerMarket.objects.create(farmer_id=farmer_id, market=market, stall_label=stall_label)

    try:
        return run_with_retry_if_top_level(_execute)
    except IntegrityError as exc:  # UNIQUE (farmer, market) is the last guard
        raise _invalid({"market_id": ["You already sell at this market."]}) from exc


def update_stall_label(*, farmer_id: int, farmer_market_id: int, stall_label: str) -> FarmerMarket:
    """FA-06."""

    def _execute() -> FarmerMarket:
        with transaction.atomic():
            farmer_market = _lock_farmer_market(farmer_id, farmer_market_id)
            if farmer_market.stall_label != stall_label:
                farmer_market.stall_label = stall_label
                farmer_market.save(update_fields=["stall_label", "updated_at"])
            return farmer_market

    return run_with_retry_if_top_level(_execute)


def leave_market(*, farmer_id: int, farmer_market_id: int) -> None:
    """FA-07: blocked while open orders exist at this market; slots are removed with it."""
    expire_overdue_orders(farmer_id=farmer_id)

    def _execute() -> None:
        with transaction.atomic():
            _lock_profile(farmer_id)
            farmer_market = _lock_farmer_market(farmer_id, farmer_market_id)
            blocking = _open_order_ids(farmer_id=farmer_id, market_id=farmer_market.market_id)
            if blocking:
                raise UnprocessableEntityError(
                    "You still have open orders at this market. Please handle them first.",
                    code=ErrorCode.RESOURCE_IN_USE,
                    errors={"order_ids": blocking},
                )
            # Past orders keep their data: orders.pickup_slot is SET_NULL, market/stall are snapshots.
            # Slots are deleted one by one first so the audit trail records each of them (v1.8).
            reason = f"Farmer left market #{farmer_market.market_id}"
            for slot in PickupSlot.objects.select_for_update(of=("self",)).filter(
                farmer_market=farmer_market
            ).order_by("id"):
                delete_with_history(slot, reason=reason)
            delete_with_history(farmer_market, reason=reason)

    run_with_retry_if_top_level(_execute)


# --- Pickup slots (FA-08, FA-09, FA-10) ---


def _validate_slot(
    *,
    profile: FarmerProfile,
    farmer_market: FarmerMarket,
    day_of_week: int,
    start_time: time,
    end_time: time,
    is_active: bool,
    check_overlap: bool = True,
    exclude_slot_id: int | None = None,
) -> None:
    """D-013 / D-022 / D-031 rules. An inactive slot only needs a valid time range, so a farmer can
    always switch off a slot that no longer fits the market schedule."""
    errors: dict[str, list[str]] = {}
    market = farmer_market.market
    if end_time <= start_time:
        errors["end_time"] = ["End time must be after start time"]

    if is_active:
        if not market.is_active:
            errors["farmer_market_id"] = ["This market is not active."]
        if not MarketOperatingDay.objects.filter(market=market, day_of_week=day_of_week).exists():
            errors["day_of_week"] = ["The market is not open on this day."]
        elif day_of_week not in (profile.operating_days or []):
            errors["day_of_week"] = [
                "This day is not one of your operating days. Update your operating days in your profile first."
            ]
        if start_time < market.open_time:
            errors["start_time"] = [f"The market opens at {market.open_time.strftime('%H:%M')}."]
        if end_time > market.close_time:
            errors.setdefault("end_time", []).append(
                f"The market closes at {market.close_time.strftime('%H:%M')}."
            )

    if check_overlap and "end_time" not in errors:
        # Decision (b) v1.8: no overlap inside the same market on the same day; another market is fine.
        overlapping = PickupSlot.objects.filter(
            farmer_market=farmer_market,
            day_of_week=day_of_week,
            start_time__lt=end_time,
            end_time__gt=start_time,
        )
        if exclude_slot_id is not None:
            overlapping = overlapping.exclude(pk=exclude_slot_id)
        clash = overlapping.order_by("start_time").first()
        if clash is not None:
            errors.setdefault("start_time", []).append(
                f"Overlaps your {clash.start_time.strftime('%H:%M')}-{clash.end_time.strftime('%H:%M')} slot "
                "at this market."
            )
    if errors:
        raise _invalid(errors)


def create_pickup_slot(
    *, farmer_id: int, farmer_market_id: int, day_of_week: int, start_time: time, end_time: time
) -> PickupSlot:
    """FA-08."""

    def _execute() -> PickupSlot:
        with transaction.atomic():
            profile = _lock_profile(farmer_id)
            farmer_market = (
                FarmerMarket.objects.select_for_update(of=("self",))
                .select_related("market")
                .filter(pk=farmer_market_id, farmer_id=farmer_id)
                .first()
            )
            if farmer_market is None:
                raise _invalid({"farmer_market_id": ["Market not found in your list."]})
            _validate_slot(
                profile=profile,
                farmer_market=farmer_market,
                day_of_week=day_of_week,
                start_time=start_time,
                end_time=end_time,
                is_active=True,
            )
            return PickupSlot.objects.create(
                farmer_market=farmer_market, day_of_week=day_of_week, start_time=start_time, end_time=end_time
            )

    return run_with_retry_if_top_level(_execute)


def _lock_slot(farmer_id: int, slot_id: int) -> tuple[FarmerProfile, FarmerMarket, PickupSlot]:
    profile = _lock_profile(farmer_id)
    farmer_market_id = (
        PickupSlot.objects.filter(pk=slot_id, farmer_market__farmer_id=farmer_id)
        .values_list("farmer_market_id", flat=True)
        .first()
    )
    if farmer_market_id is None:
        raise ResourceNotFoundError("Pickup slot not found.", code=ErrorCode.NOT_FOUND)
    farmer_market = _lock_farmer_market(farmer_id, farmer_market_id)
    slot = PickupSlot.objects.select_for_update(of=("self",)).get(pk=slot_id)
    return profile, farmer_market, slot


def update_pickup_slot(*, farmer_id: int, slot_id: int, changes: dict[str, Any]) -> PickupSlot:
    """FA-09. Turning a slot back on (e.g. after a market schedule change, D-022) re-checks every rule."""

    def _execute() -> PickupSlot:
        with transaction.atomic():
            profile, farmer_market, slot = _lock_slot(farmer_id, slot_id)
            merged = {
                "day_of_week": changes.get("day_of_week", slot.day_of_week),
                "start_time": changes.get("start_time", slot.start_time),
                "end_time": changes.get("end_time", slot.end_time),
                "is_active": changes.get("is_active", slot.is_active),
            }
            _validate_slot(
                profile=profile,
                farmer_market=farmer_market,
                exclude_slot_id=slot.pk,
                # Switching a slot off must always work, even if it no longer fits (D-022).
                check_overlap=merged["is_active"] or bool({"day_of_week", "start_time", "end_time"} & set(changes)),
                **merged,
            )
            changed = [field for field, value in merged.items() if getattr(slot, field) != value]
            for field in changed:
                setattr(slot, field, merged[field])
            if changed:
                slot.save(update_fields=[*changed, "updated_at"])
            return slot

    return run_with_retry_if_top_level(_execute)


def delete_pickup_slot(*, farmer_id: int, slot_id: int) -> None:
    """FA-10: blocked while open orders use the slot; switching it off is the alternative."""
    expire_overdue_orders(farmer_id=farmer_id)

    def _execute() -> None:
        with transaction.atomic():
            _, _, slot = _lock_slot(farmer_id, slot_id)
            blocking = _open_order_ids(pickup_slot=slot)
            if blocking:
                raise UnprocessableEntityError(
                    "Open orders still use this pickup slot. Turn the slot off instead, "
                    "or handle those orders first.",
                    code=ErrorCode.RESOURCE_IN_USE,
                    errors={"order_ids": blocking},
                )
            slot.delete()

    run_with_retry_if_top_level(_execute)


# --- Time off (FA-32, FA-33, D-023) ---


def create_farmer_closure(*, farmer_id: int, start_date: date, end_date: date, reason: str | None) -> FarmerClosure:
    """FA-32: no past start, no overlap with another closure, no open order inside the range."""
    errors: dict[str, list[str]] = {}
    if start_date < timezone.localdate():
        errors["start_date"] = ["The start date cannot be in the past."]
    if end_date < start_date:
        errors["end_date"] = ["The end date must be on or after the start date."]
    if errors:
        raise _invalid(errors)
    expire_overdue_orders(farmer_id=farmer_id)

    def _execute() -> FarmerClosure:
        with transaction.atomic():
            _lock_profile(farmer_id)  # serializes the overlap check (§5.2, D-023)
            clash = (
                FarmerClosure.objects.filter(
                    farmer_id=farmer_id, start_date__lte=end_date, end_date__gte=start_date
                )
                .order_by("start_date")
                .first()
            )
            if clash is not None:
                raise _invalid(
                    {
                        "start_date": [
                            f"Overlaps your time off from {clash.start_date.isoformat()} "
                            f"to {clash.end_date.isoformat()}."
                        ]
                    }
                )
            blocking = _open_order_ids(
                farmer_id=farmer_id, pickup_date__gte=start_date, pickup_date__lte=end_date
            )
            if blocking:
                raise UnprocessableEntityError(
                    "You have open orders during this time off. Please handle them first.",
                    code=ErrorCode.RESOURCE_IN_USE,
                    errors={"order_ids": blocking},
                )
            return FarmerClosure.objects.create(
                farmer_id=farmer_id, start_date=start_date, end_date=end_date, reason=reason
            )

    return run_with_retry_if_top_level(_execute)


def delete_farmer_closure(*, farmer_id: int, closure_id: int) -> None:
    """FA-33."""
    deleted, _ = FarmerClosure.objects.filter(pk=closure_id, farmer_id=farmer_id).delete()
    if not deleted:
        raise ResourceNotFoundError("Time off not found.", code=ErrorCode.NOT_FOUND)
