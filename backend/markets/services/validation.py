from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.utils import timezone

from marketlink_core.exceptions import ErrorCode, UnprocessableEntityError
from markets.models import FarmerClosure, Market, MarketClosure, MarketOperatingDay, PickupSlot

BOOKING_HORIZON_DAYS = 7


@dataclass(frozen=True)
class ValidatedPickupSchedule:
    slot: PickupSlot
    start_at: datetime
    end_at: datetime
    cutoff_at: datetime


def validate_pickup_date(
    *,
    farmer_id: int,
    market_id: int,
    pickup_date: date,
    pickup_slot_id: int,
) -> ValidatedPickupSchedule:
    """Check a pickup date against A-019 (PU-08, CU-04, CU-07, FA-34).

    Rules (1)-(5a) -> 422 SLOT_NOT_AVAILABLE; now >= cutoff_at -> 422 CUTOFF_PASSED.
    """
    now = timezone.now()
    current_tz = timezone.get_current_timezone()
    today = timezone.localtime(now).date()
    max_booking_date = today + timedelta(days=BOOKING_HORIZON_DAYS)

    if pickup_date < today or pickup_date > max_booking_date:
        raise UnprocessableEntityError(
            f"Pickup date must be between {today.strftime('%Y-%m-%d')} and {max_booking_date.strftime('%Y-%m-%d')}.",
            code=ErrorCode.SLOT_NOT_AVAILABLE,
        )

    weekday = pickup_date.isoweekday()

    # (4) market is_active is checked on its own so the message tells the real reason.
    if not Market.objects.filter(id=market_id, is_active=True).exists():
        raise UnprocessableEntityError(
            "The market is not active.",
            code=ErrorCode.SLOT_NOT_AVAILABLE,
        )

    # (1a) market day
    if not MarketOperatingDay.objects.filter(market_id=market_id, day_of_week=weekday).exists():
        raise UnprocessableEntityError(
            "The market is not operating on the selected pickup date.",
            code=ErrorCode.SLOT_NOT_AVAILABLE,
        )

    if MarketClosure.objects.filter(
        market_id=market_id,
        start_date__lte=pickup_date,
        end_date__gte=pickup_date,
    ).exists():
        raise UnprocessableEntityError(
            "The market is closed on the selected pickup date.",
            code=ErrorCode.SLOT_NOT_AVAILABLE,
        )

    if FarmerClosure.objects.filter(
        farmer_id=farmer_id,
        start_date__lte=pickup_date,
        end_date__gte=pickup_date,
    ).exists():
        raise UnprocessableEntityError(
            "The stall is closed on the selected pickup date.",
            code=ErrorCode.SLOT_NOT_AVAILABLE,
        )

    try:
        slot = PickupSlot.objects.select_related("farmer_market__farmer").get(
            id=pickup_slot_id,
            farmer_market__farmer_id=farmer_id,
            farmer_market__market_id=market_id,
        )
    except PickupSlot.DoesNotExist:
        raise UnprocessableEntityError(
            "The selected pickup slot is not available for this stall at this market.",
            code=ErrorCode.SLOT_NOT_AVAILABLE,
        )

    if not slot.is_active:
        raise UnprocessableEntityError(
            "The selected pickup slot is not active.",
            code=ErrorCode.SLOT_NOT_AVAILABLE,
        )

    if weekday != slot.day_of_week:
        raise UnprocessableEntityError(
            f"The pickup date is not a {slot.get_day_of_week_display()}.",
            code=ErrorCode.SLOT_NOT_AVAILABLE,
        )

    # (1b) farmer operating day (D-031). Missing or broken data never lets a date through.
    farmer = slot.farmer_market.farmer
    operating_days = farmer.operating_days if isinstance(farmer.operating_days, list) else []
    if weekday not in operating_days:
        raise UnprocessableEntityError(
            "The stall does not operate on the selected day.",
            code=ErrorCode.SLOT_NOT_AVAILABLE,
        )

    start_at = timezone.make_aware(datetime.combine(pickup_date, slot.start_time), current_tz)
    end_at = timezone.make_aware(datetime.combine(pickup_date, slot.end_time), current_tz)
    cutoff_hours = farmer.order_cutoff_hours
    cutoff_at = start_at - timedelta(hours=cutoff_hours)

    if now >= cutoff_at:
        raise UnprocessableEntityError(
            "The cutoff time for this pickup slot has already passed.",
            code=ErrorCode.CUTOFF_PASSED,
        )

    return ValidatedPickupSchedule(
        slot=slot,
        start_at=start_at,
        end_at=end_at,
        cutoff_at=cutoff_at,
    )
