from datetime import datetime, time, timedelta
from types import SimpleNamespace
from unittest import mock

import pytest
from django.utils import timezone

from accounts.models import FarmerProfile
from markets.models import FarmerClosure, MarketClosure
from orders.exceptions import CutoffPassedError, SlotNotAvailableError
from orders.services.pickup_service import list_pickup_options, resolve_pickup
from tests_support.factories import make_farmer, make_market, make_slot


def _local(day, at):
    return timezone.make_aware(datetime.combine(day, at))


@pytest.fixture
def shop(db):
    today = timezone.localdate()
    pickup_date = today + timedelta(days=3)
    farmer = make_farmer(cutoff_hours=12)
    market = make_market()
    slot = make_slot(farmer=farmer, market=market, day_of_week=pickup_date.isoweekday())
    return SimpleNamespace(now=_local(today, time(9, 0)), date=pickup_date, farmer=farmer, market=market, slot=slot)


def _resolve(shop, **overrides):
    args = {"farmer": shop.farmer, "pickup_slot_id": shop.slot.id, "pickup_date": shop.date, "now": shop.now}
    args.update(overrides)
    with mock.patch("django.utils.timezone.now", return_value=args["now"]):
        return resolve_pickup(**args)


class TestResolvePickup:
    def test_builds_snapshot_window(self, shop):
        window = _resolve(shop)

        start = _local(shop.date, time(8, 0))
        assert window.slot == shop.slot
        assert window.market == shop.market
        assert window.stall_label == "Row B, stall 12"
        assert (window.pickup_start_at, window.pickup_end_at) == (start, _local(shop.date, time(10, 0)))
        assert window.cutoff_at == start - timedelta(hours=12)

    def test_wrong_weekday_is_rejected(self, shop):
        with pytest.raises(SlotNotAvailableError):
            _resolve(shop, pickup_date=shop.date + timedelta(days=1))

    @pytest.mark.parametrize("days", [7, -7])
    def test_date_outside_booking_horizon_is_rejected(self, shop, days):
        with pytest.raises(SlotNotAvailableError):
            _resolve(shop, pickup_date=shop.date + timedelta(days=days))

    def test_inactive_slot_is_rejected(self, shop):
        shop.slot.is_active = False
        shop.slot.save()

        with pytest.raises(SlotNotAvailableError):
            _resolve(shop)

    def test_inactive_market_is_rejected(self, shop):
        shop.market.is_active = False
        shop.market.save()

        with pytest.raises(SlotNotAvailableError):
            _resolve(shop)

    def test_market_closed_on_that_weekday_is_rejected(self, shop):
        shop.market.operating_days.filter(day_of_week=shop.date.isoweekday()).delete()

        with pytest.raises(SlotNotAvailableError):
            _resolve(shop)

    def test_market_closure_is_rejected(self, shop):
        MarketClosure.objects.create(market=shop.market, start_date=shop.date, end_date=shop.date)

        with pytest.raises(SlotNotAvailableError):
            _resolve(shop)

    def test_farmer_closure_is_rejected(self, shop):
        FarmerClosure.objects.create(farmer=shop.farmer, start_date=shop.date - timedelta(days=1), end_date=shop.date)

        with pytest.raises(SlotNotAvailableError):
            _resolve(shop)

    def test_day_the_farmer_does_not_operate_is_rejected(self, shop):
        shop.farmer.operating_days = [day for day in range(1, 8) if day != shop.date.isoweekday()]
        shop.farmer.save()

        with pytest.raises(SlotNotAvailableError):
            _resolve(shop)

    def test_slot_of_another_farmer_is_rejected(self, shop):
        with pytest.raises(SlotNotAvailableError):
            _resolve(shop, farmer=make_farmer())

    def test_at_cutoff_is_too_late(self, shop):
        cutoff = _local(shop.date, time(8, 0)) - timedelta(hours=12)

        with pytest.raises(CutoffPassedError):
            _resolve(shop, now=cutoff)
        assert _resolve(shop, now=cutoff - timedelta(minutes=1)).cutoff_at == cutoff


class TestListPickupOptions:
    def test_groups_bookable_dates_by_market(self, shop):
        options = list_pickup_options(farmer=shop.farmer, now=shop.now)

        assert options == [
            {
                "market_id": shop.market.id,
                "market_name": shop.market.name,
                "stall_label": "Row B, stall 12",
                "latitude": 10.772345,
                "longitude": 106.698765,
                "dates": [
                    {
                        "date": shop.date.isoformat(),
                        "day_of_week": shop.date.isoweekday(),
                        "slots": [
                            {
                                "pickup_slot_id": shop.slot.id,
                                "start_time": "08:00",
                                "end_time": "10:00",
                                "cutoff_at": timezone.localtime(
                                    _local(shop.date, time(8, 0)) - timedelta(hours=12)
                                ).isoformat(),
                                "is_bookable": True,
                            }
                        ],
                    }
                ],
            }
        ]

    def test_skips_closed_days(self, shop):
        FarmerClosure.objects.create(farmer=shop.farmer, start_date=shop.date, end_date=shop.date)

        assert list_pickup_options(farmer=shop.farmer, now=shop.now) == []

    def test_skips_days_the_farmer_does_not_operate(self, shop):
        shop.farmer.operating_days = [day for day in range(1, 8) if day != shop.date.isoweekday()]
        shop.farmer.save()

        assert list_pickup_options(farmer=shop.farmer, now=shop.now) == []

    def test_farmer_without_operating_days_offers_nothing(self, shop):
        FarmerProfile.objects.filter(pk=shop.farmer.pk).update(operating_days=[])
        shop.farmer.refresh_from_db()

        assert list_pickup_options(farmer=shop.farmer, now=shop.now) == []

    def test_skips_slots_past_cutoff(self, shop):
        late = _local(shop.date, time(8, 0)) - timedelta(hours=11)

        assert list_pickup_options(farmer=shop.farmer, now=late) == []

    def test_respects_requested_window(self, shop):
        assert list_pickup_options(farmer=shop.farmer, days=2, now=shop.now) == []
