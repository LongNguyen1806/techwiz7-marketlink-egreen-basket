from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser, FarmerProfile, Role, RoleCode
from marketlink_core.exceptions import ErrorCode, UnprocessableEntityError
from markets.models import FarmerClosure, FarmerMarket, Market, MarketClosure, MarketOperatingDay, PickupSlot
from markets.services.validation import validate_pickup_date


class MarketsValidationTestCase(TestCase):
    def setUp(self):
        farmer_role, _ = Role.objects.get_or_create(
            code=RoleCode.FARMER, defaults={"name": "Farmer"}
        )
        self.farmer_user = CustomUser.objects.create(
            email="farmer_val@marketlink.local",
            role=farmer_role,
        )
        self.farmer = FarmerProfile.objects.create(
            operating_days=[1, 2, 3, 4, 5, 6, 7],
            user=self.farmer_user,
            stall_name="Validation Stall",
            contact_person="Tran Van Val",
            phone="0988111222",
            address="123 Val Road",
            order_cutoff_hours=6,
        )

        self.market = Market.objects.create(
            name="Val Market",
            address="456 Val Blvd",
            latitude=Decimal("10.7769"),
            longitude=Decimal("106.7009"),
            open_time="06:00:00",
            close_time="20:00:00",
            is_active=True,
        )
        self.farmer_market = FarmerMarket.objects.create(
            farmer=self.farmer,
            market=self.market,
            stall_label="Stall V1",
        )

        for day in range(1, 8):
            MarketOperatingDay.objects.create(market=self.market, day_of_week=day)

        self.target_date = timezone.localdate() + timedelta(days=2)
        self.slot = PickupSlot.objects.create(
            farmer_market=self.farmer_market,
            day_of_week=self.target_date.isoweekday(),
            start_time="14:00:00",
            end_time="16:00:00",
            is_active=True,
        )

    def test_valid_pickup_schedule(self):
        schedule = validate_pickup_date(
            farmer_id=self.farmer.pk,
            market_id=self.market.pk,
            pickup_date=self.target_date,
            pickup_slot_id=self.slot.pk,
        )
        self.assertEqual(schedule.slot.pk, self.slot.pk)
        self.assertEqual(schedule.start_at.date(), self.target_date)
        self.assertEqual(schedule.cutoff_at, schedule.start_at - timedelta(hours=6))

    def test_pickup_date_beyond_horizon_fails(self):
        beyond_date = timezone.localdate() + timedelta(days=8)
        far_slot = PickupSlot.objects.create(
            farmer_market=self.farmer_market,
            day_of_week=beyond_date.isoweekday(),
            start_time="14:00:00",
            end_time="16:00:00",
            is_active=True,
        )

        with self.assertRaises(UnprocessableEntityError) as ctx:
            validate_pickup_date(
                farmer_id=self.farmer.pk,
                market_id=self.market.pk,
                pickup_date=beyond_date,
                pickup_slot_id=far_slot.pk,
            )
        self.assertEqual(ctx.exception.code, ErrorCode.SLOT_NOT_AVAILABLE)

    def test_pickup_date_in_past_fails(self):
        past_date = timezone.localdate() - timedelta(days=1)
        with self.assertRaises(UnprocessableEntityError) as ctx:
            validate_pickup_date(
                farmer_id=self.farmer.pk,
                market_id=self.market.pk,
                pickup_date=past_date,
                pickup_slot_id=self.slot.pk,
            )
        self.assertEqual(ctx.exception.code, ErrorCode.SLOT_NOT_AVAILABLE)

    def test_market_closure_fails(self):
        MarketClosure.objects.create(
            market=self.market,
            start_date=self.target_date,
            end_date=self.target_date,
            reason="Public holiday renovation",
        )

        with self.assertRaises(UnprocessableEntityError) as ctx:
            validate_pickup_date(
                farmer_id=self.farmer.pk,
                market_id=self.market.pk,
                pickup_date=self.target_date,
                pickup_slot_id=self.slot.pk,
            )
        self.assertEqual(ctx.exception.code, ErrorCode.SLOT_NOT_AVAILABLE)

    def test_farmer_closure_fails(self):
        FarmerClosure.objects.create(
            farmer=self.farmer,
            start_date=self.target_date,
            end_date=self.target_date,
            reason="Family event",
        )

        with self.assertRaises(UnprocessableEntityError) as ctx:
            validate_pickup_date(
                farmer_id=self.farmer.pk,
                market_id=self.market.pk,
                pickup_date=self.target_date,
                pickup_slot_id=self.slot.pk,
            )
        self.assertEqual(ctx.exception.code, ErrorCode.SLOT_NOT_AVAILABLE)

    def test_cutoff_passed_fails(self):
        self.farmer.order_cutoff_hours = 72
        self.farmer.save()

        with self.assertRaises(UnprocessableEntityError) as ctx:
            validate_pickup_date(
                farmer_id=self.farmer.pk,
                market_id=self.market.pk,
                pickup_date=self.target_date,
                pickup_slot_id=self.slot.pk,
            )
        self.assertEqual(ctx.exception.code, ErrorCode.CUTOFF_PASSED)


    def _assert_slot_not_available(self, message_part, **overrides):
        kwargs = {
            "farmer_id": self.farmer.pk,
            "market_id": self.market.pk,
            "pickup_date": self.target_date,
            "pickup_slot_id": self.slot.pk,
            **overrides,
        }
        with self.assertRaises(UnprocessableEntityError) as ctx:
            validate_pickup_date(**kwargs)
        self.assertEqual(ctx.exception.code, ErrorCode.SLOT_NOT_AVAILABLE)
        self.assertIn(message_part, str(ctx.exception.detail))

    def test_farmer_non_operating_day_fails(self):
        weekday = self.target_date.isoweekday()
        self.farmer.operating_days = [day for day in range(1, 8) if day != weekday]
        self.farmer.save()
        self._assert_slot_not_available("does not operate")

    def test_invalid_operating_days_in_db_fail_closed(self):
        FarmerProfile.objects.filter(pk=self.farmer.pk).update(operating_days=[])
        self._assert_slot_not_available("does not operate")

    def test_inactive_market_fails_with_own_message(self):
        Market.objects.filter(pk=self.market.pk).update(is_active=False)
        self._assert_slot_not_available("market is not active")

    def test_market_not_operating_day_fails(self):
        MarketOperatingDay.objects.filter(
            market=self.market, day_of_week=self.target_date.isoweekday()
        ).delete()
        self._assert_slot_not_available("market is not operating")

    def test_inactive_slot_fails(self):
        PickupSlot.objects.filter(pk=self.slot.pk).update(is_active=False)
        self._assert_slot_not_available("slot is not active")

    def test_wrong_weekday_for_slot_fails(self):
        self._assert_slot_not_available(
            "The pickup date is not a", pickup_date=self.target_date + timedelta(days=1)
        )

    def test_slot_of_other_farmer_fails(self):
        other_user = CustomUser.objects.create(
            email="farmer_val_other@marketlink.local", role=self.farmer_user.role
        )
        other_farmer = FarmerProfile.objects.create(
            user=other_user,
            stall_name="Other Stall",
            contact_person="Le Van Other",
            phone="0988111333",
            address="789 Other Road",
            operating_days=[1, 2, 3, 4, 5, 6, 7],
        )
        other_slot = PickupSlot.objects.create(
            farmer_market=FarmerMarket.objects.create(
                farmer=other_farmer, market=self.market, stall_label="Stall V2"
            ),
            day_of_week=self.target_date.isoweekday(),
            start_time="14:00:00",
            end_time="16:00:00",
            is_active=True,
        )
        self._assert_slot_not_available("not available for this stall", pickup_slot_id=other_slot.pk)
