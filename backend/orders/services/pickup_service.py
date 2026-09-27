from dataclasses import dataclass
from datetime import date, datetime, timedelta

from django.utils import timezone

from marketlink_core.exceptions import ErrorCode, UnprocessableEntityError
from markets.models import FarmerClosure, MarketClosure, PickupSlot
from markets.services.validation import validate_pickup_date
from orders.constants import BOOKING_HORIZON_DAYS
from orders.exceptions import CutoffPassedError, SlotNotAvailableError

# A-019 / D-031: a pickup date is valid only if it is a market day and one of the farmer's operating days,
# neither the market nor the farmer is on a closure, the slot and market are active, it is inside the
# booking horizon and before cutoff.


@dataclass(frozen=True)
class PickupWindow:
    slot: PickupSlot
    pickup_date: date
    pickup_start_at: datetime
    pickup_end_at: datetime
    cutoff_at: datetime

    @property
    def market(self):
        return self.slot.farmer_market.market

    @property
    def stall_label(self) -> str:
        return self.slot.farmer_market.stall_label


def pickup_window(slot: PickupSlot, farmer, pickup_date: date) -> PickupWindow:
    start = timezone.make_aware(datetime.combine(pickup_date, slot.start_time))
    return PickupWindow(
        slot=slot,
        pickup_date=pickup_date,
        pickup_start_at=start,
        pickup_end_at=timezone.make_aware(datetime.combine(pickup_date, slot.end_time)),
        cutoff_at=start - timedelta(hours=farmer.order_cutoff_hours),
    )


def _active_slots(farmer):
    return (
        PickupSlot.objects.select_related("farmer_market__market")
        .prefetch_related("farmer_market__market__operating_days")
        .filter(farmer_market__farmer=farmer, is_active=True, farmer_market__market__is_active=True)
    )


def _closures(farmer, market_ids, first: date, last: date):
    market_ranges: dict[int, list] = {}
    for closure in MarketClosure.objects.filter(market_id__in=market_ids, start_date__lte=last, end_date__gte=first):
        market_ranges.setdefault(closure.market_id, []).append((closure.start_date, closure.end_date))
    farmer_ranges = [
        (closure.start_date, closure.end_date)
        for closure in FarmerClosure.objects.filter(farmer=farmer, start_date__lte=last, end_date__gte=first)
    ]
    return market_ranges, farmer_ranges


def _covered(ranges, day: date) -> bool:
    return any(start <= day <= end for start, end in ranges)


def _farmer_operates_on(farmer, day: date) -> bool:
    # D-031 (v1.7): the date must also be one of the farmer's operating days (JSON list of ISO weekdays 1-7).
    return day.isoweekday() in (farmer.operating_days or [])


def _is_open_on(slot: PickupSlot, day: date, market_ranges, farmer_ranges, farmer) -> bool:
    market = slot.farmer_market.market
    operating_days = {operating.day_of_week for operating in market.operating_days.all()}
    return (
        day.isoweekday() == slot.day_of_week
        and slot.day_of_week in operating_days
        and _farmer_operates_on(farmer, day)
        and not _covered(market_ranges.get(market.id, []), day)
        and not _covered(farmer_ranges, day)
    )


def check_customer_pickup_date(*, farmer, pickup_date: date, now=None) -> None:
    """The one date check validate_pickup_date() does not share yet, for CU-04 and CU-07.

    PU-08 offers today .. today + BOOKING_HORIZON_DAYS - 1, while validate_pickup_date() still accepts one
    day more; kept here until the Farmer branch settles the horizon. Operating days (D-031) are checked there.
    """
    today = timezone.localdate(now or timezone.now())
    if not today <= pickup_date < today + timedelta(days=BOOKING_HORIZON_DAYS):
        raise SlotNotAvailableError()


def resolve_pickup(*, farmer, pickup_slot_id: int, pickup_date: date, now=None) -> PickupWindow:
    """CU-04: the Farmer branch's validate_pickup_date() plus check_customer_pickup_date()."""
    slot = _active_slots(farmer).filter(pk=pickup_slot_id).first()
    if slot is None:
        raise SlotNotAvailableError()
    check_customer_pickup_date(farmer=farmer, pickup_date=pickup_date, now=now)
    try:
        schedule = validate_pickup_date(
            farmer_id=farmer.pk,
            market_id=slot.farmer_market.market_id,
            pickup_date=pickup_date,
            pickup_slot_id=slot.pk,
        )
    except UnprocessableEntityError as exc:
        raise (CutoffPassedError() if exc.code == ErrorCode.CUTOFF_PASSED else SlotNotAvailableError()) from exc
    return PickupWindow(
        slot=slot,
        pickup_date=pickup_date,
        pickup_start_at=schedule.start_at,
        pickup_end_at=schedule.end_at,
        cutoff_at=schedule.cutoff_at,
    )


def list_pickup_options(*, farmer, date_from: date | None = None, days: int = BOOKING_HORIZON_DAYS, now=None) -> list[dict]:
    now = now or timezone.now()
    today = timezone.localdate(now)
    first = max(date_from or today, today)
    last = min(first + timedelta(days=days - 1), today + timedelta(days=BOOKING_HORIZON_DAYS - 1))
    slots = list(_active_slots(farmer).order_by("farmer_market__market__name", "start_time"))
    if first > last or not slots:
        return []
    market_ranges, farmer_ranges = _closures(farmer, {slot.farmer_market.market_id for slot in slots}, first, last)

    options: dict[int, dict] = {}
    day = first
    while day <= last:
        for slot in slots:
            if not _is_open_on(slot, day, market_ranges, farmer_ranges, farmer):
                continue
            window = pickup_window(slot, farmer, day)
            # PU-08 v1.1 / A-003: slots whose cutoff has passed are not offered at all.
            if now >= window.cutoff_at:
                continue
            market = slot.farmer_market.market
            option = options.setdefault(market.id, {
                "market_id": market.id,
                "market_name": market.name,
                "stall_label": slot.farmer_market.stall_label,
                "latitude": float(market.latitude),
                "longitude": float(market.longitude),
                "dates": {},
            })
            entry = option["dates"].setdefault(day, {"date": day.isoformat(), "day_of_week": day.isoweekday(), "slots": []})
            entry["slots"].append({
                "pickup_slot_id": slot.id,
                "start_time": slot.start_time.strftime("%H:%M"),
                "end_time": slot.end_time.strftime("%H:%M"),
                "cutoff_at": timezone.localtime(window.cutoff_at).isoformat(),
                "is_bookable": True,
            })
        day += timedelta(days=1)
    return [{**option, "dates": list(option["dates"].values())} for option in options.values()]
