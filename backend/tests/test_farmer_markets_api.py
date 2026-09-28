from datetime import datetime, time, timedelta
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CustomUser, CustomerProfile, FarmerProfile, FarmerStatus, Role, RoleCode
from marketlink_core.exceptions import ErrorCode
from markets.models import FarmerMarket, Market, MarketOperatingDay, PickupSlot
from orders.models import Order, OrderStatus

MARKETS_URL = "/api/farmer/markets/"
SLOTS_URL = "/api/farmer/pickup-slots/"


class FarmerMarketsAndSlotsAPITestCase(TestCase):
    """F3: FA-04 -> FA-10 (D-013, D-022, D-026, D-031; decisions (a), (b) v1.8)."""

    def setUp(self):
        self.client = APIClient()
        farmer_role, _ = Role.objects.get_or_create(code=RoleCode.FARMER, defaults={"name": "Farmer"})
        customer_role, _ = Role.objects.get_or_create(code=RoleCode.CUSTOMER, defaults={"name": "Customer"})

        self.farmer_user = CustomUser.objects.create(email="f3_farmer@marketlink.local", role=farmer_role)
        self.farmer = FarmerProfile.objects.create(
            user=self.farmer_user,
            stall_name="F3 Stall",
            contact_person="Tran Van F",
            phone="0977100100",
            address="1 F3 Road",
            status=FarmerStatus.APPROVED,
            operating_days=[1, 3, 5],
        )
        other_user = CustomUser.objects.create(email="f3_other@marketlink.local", role=farmer_role)
        self.other_farmer = FarmerProfile.objects.create(
            user=other_user,
            stall_name="Other F3",
            contact_person="Le Van O",
            phone="0977100200",
            address="2 F3 Road",
            status=FarmerStatus.APPROVED,
            operating_days=[1, 2, 3, 4, 5, 6, 7],
        )
        self.customer = CustomUser.objects.create(email="f3_customer@marketlink.local", role=customer_role)
        CustomerProfile.objects.create(user=self.customer, full_name="Khach F3", phone="0911100100", address="3 Road")

        self.market_a = self._market("Market A", days=range(1, 7), open_at="06:00", close_at="12:00")
        self.market_b = self._market("Market B", days=[1, 3, 5], open_at="05:00", close_at="10:00")
        self.market_closed = self._market("Market Closed", days=[1, 3, 5], open_at="06:00", close_at="12:00")
        self.market_closed.is_active = False
        self.market_closed.save(update_fields=["is_active"])

        self.fm_a = FarmerMarket.objects.create(farmer=self.farmer, market=self.market_a, stall_label="Row A1")
        self.slot_mon = PickupSlot.objects.create(
            farmer_market=self.fm_a, day_of_week=1, start_time="07:00", end_time="09:00"
        )
        self.other_fm = FarmerMarket.objects.create(
            farmer=self.other_farmer, market=self.market_a, stall_label="Row Z9"
        )
        self.other_slot = PickupSlot.objects.create(
            farmer_market=self.other_fm, day_of_week=2, start_time="07:00", end_time="09:00"
        )
        self.client.force_authenticate(user=self.farmer_user)

    def _market(self, name, *, days, open_at, close_at) -> Market:
        market = Market.objects.create(
            name=name,
            address=f"{name} address",
            latitude=Decimal("10.770000"),
            longitude=Decimal("106.700000"),
            open_time=open_at,
            close_time=close_at,
        )
        for day in days:
            MarketOperatingDay.objects.create(market=market, day_of_week=day)
        return market

    def _order(self, *, market, slot, status=OrderStatus.PLACED, days_ahead=3) -> Order:
        pickup_date = timezone.localdate() + timedelta(days=days_ahead)
        start_at = timezone.make_aware(datetime.combine(pickup_date, time(7, 0)), timezone.get_current_timezone())
        return Order.objects.create(
            customer=self.customer,
            farmer=self.farmer,
            market=market,
            pickup_slot=slot,
            stall_label="Row A1",
            pickup_date=pickup_date,
            pickup_start_at=start_at,
            pickup_end_at=start_at + timedelta(hours=2),
            cutoff_at=start_at - timedelta(hours=12),
            total_amount=Decimal("5.00"),
            status=status,
        )

    def _slot(self, **body):
        payload = {"farmer_market_id": self.fm_a.pk, "day_of_week": 3, "start_time": "07:00", "end_time": "09:00"}
        payload.update(body)
        return self.client.post(SLOTS_URL, payload, format="json")


    def test_list_markets(self):
        self._order(market=self.market_a, slot=self.slot_mon)
        self._order(market=self.market_a, slot=self.slot_mon, status=OrderStatus.COMPLETED)
        res = self.client.get(MARKETS_URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["data"]), 1)
        item = res.data["data"][0]
        self.assertEqual(
            set(item), {"id", "market", "is_market_active", "status", "stall_label", "slots", "open_order_count"}
        )
        self.assertEqual(item["open_order_count"], 1)
        self.assertEqual(item["stall_label"], "Row A1")
        self.assertEqual(item["slots"][0]["start_time"], "07:00")
        market = item["market"]
        self.assertEqual(market["operating_days"], [1, 2, 3, 4, 5, 6])
        self.assertEqual((market["open_time"], market["close_time"]), ("06:00", "12:00"))
        self.assertEqual(market["farmer_count"], 2)
        self.assertEqual(market["upcoming_closures"], [])
        self.assertIsNone(market["distance_km"])

    def test_customer_is_forbidden(self):
        self.client.force_authenticate(user=self.customer)
        self.assertEqual(self.client.get(MARKETS_URL).status_code, 403)


    def test_join_market(self):
        res = self.client.post(MARKETS_URL, {"market_id": self.market_b.pk, "stall_label": " Gate 2 "}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["data"]["stall_label"], "Gate 2")
        self.assertEqual(res.data["data"]["market"]["id"], self.market_b.pk)
        self.assertEqual(res.data["data"]["slots"], [])

    def test_join_market_rejected(self):
        cases = [
            ({"market_id": self.market_a.pk, "stall_label": "Again"}, "market_id"),
            ({"market_id": self.market_closed.pk, "stall_label": "X"}, "market_id"),
            ({"market_id": 999999, "stall_label": "X"}, "market_id"),
            ({"market_id": self.market_b.pk, "stall_label": "   "}, "stall_label"),
            ({"market_id": self.market_b.pk, "stall_label": "x" * 101}, "stall_label"),
        ]
        for body, field in cases:
            with self.subTest(body=body):
                res = self.client.post(MARKETS_URL, body, format="json")
                self.assertEqual(res.status_code, 400)
                self.assertIn(field, res.data["errors"])

    def test_database_allows_many_markets_but_one_stall_per_market(self):
        FarmerMarket.objects.create(farmer=self.farmer, market=self.market_b, stall_label="B1")
        self.assertEqual(FarmerMarket.objects.filter(farmer=self.farmer).count(), 2)
        with self.assertRaises(IntegrityError), transaction.atomic():
            FarmerMarket.objects.create(farmer=self.farmer, market=self.market_b, stall_label="B2")

    def test_suspended_farmer_can_manage_markets(self):
        FarmerProfile.objects.filter(pk=self.farmer.pk).update(status=FarmerStatus.SUSPENDED)
        res = self.client.post(MARKETS_URL, {"market_id": self.market_b.pk, "stall_label": "B1"}, format="json")
        self.assertEqual(res.status_code, 201)

    def test_update_stall_label(self):
        res = self.client.patch(f"{MARKETS_URL}{self.fm_a.pk}/", {"stall_label": "Row C3"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.fm_a.refresh_from_db()
        self.assertEqual(self.fm_a.stall_label, "Row C3")
        res = self.client.patch(f"{MARKETS_URL}{self.other_fm.pk}/", {"stall_label": "Mine"}, format="json")
        self.assertEqual(res.status_code, 404)


    def test_leave_market_blocked_by_open_order(self):
        order = self._order(market=self.market_a, slot=self.slot_mon, status=OrderStatus.ACCEPTED)
        res = self.client.delete(f"{MARKETS_URL}{self.fm_a.pk}/")
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.data["code"], ErrorCode.RESOURCE_IN_USE)
        self.assertEqual(res.data["errors"]["order_ids"], [order.pk])
        self.assertTrue(FarmerMarket.objects.filter(pk=self.fm_a.pk).exists())

    def test_leave_market_keeps_past_orders(self):
        done = self._order(market=self.market_a, slot=self.slot_mon, status=OrderStatus.COMPLETED)
        res = self.client.delete(f"{MARKETS_URL}{self.fm_a.pk}/")
        self.assertEqual(res.status_code, 204)
        self.assertFalse(PickupSlot.objects.filter(pk=self.slot_mon.pk).exists())
        done.refresh_from_db()
        self.assertIsNone(done.pickup_slot_id)
        self.assertEqual(done.stall_label, "Row A1")
        self.assertEqual(self.client.delete(f"{MARKETS_URL}{self.other_fm.pk}/").status_code, 404)


    def test_create_slot(self):
        res = self._slot()
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["data"]["day_of_week"], 3)
        self.assertEqual(res.data["data"]["end_time"], "09:00")
        self.assertTrue(res.data["data"]["is_active"])

    def test_create_slot_rule_violations(self):
        cases = [
            ({"day_of_week": 7}, "day_of_week"),
            ({"day_of_week": 2}, "day_of_week"),
            ({"start_time": "05:30"}, "start_time"),
            ({"end_time": "12:30"}, "end_time"),
            ({"start_time": "09:00", "end_time": "08:00"}, "end_time"),
            ({"day_of_week": 1, "start_time": "08:00", "end_time": "10:00"}, "start_time"),
            ({"day_of_week": 1, "start_time": "07:00", "end_time": "08:00"}, "start_time"),
            ({"farmer_market_id": 999999}, "farmer_market_id"),
            ({"start_time": "7h"}, "start_time"),
        ]
        for body, field in cases:
            with self.subTest(body=body):
                res = self._slot(**body)
                self.assertEqual(res.status_code, 400)
                self.assertIn(field, res.data["errors"])
        res = self._slot(farmer_market_id=self.other_fm.pk)
        self.assertEqual(res.status_code, 400)
        self.assertIn("farmer_market_id", res.data["errors"])

    def test_same_time_at_another_market_is_allowed(self):
        fm_b = FarmerMarket.objects.create(farmer=self.farmer, market=self.market_b, stall_label="B1")
        res = self._slot(farmer_market_id=fm_b.pk, day_of_week=1, start_time="07:00", end_time="09:00")
        self.assertEqual(res.status_code, 201)

    def test_back_to_back_slots_are_allowed(self):
        self.assertEqual(self._slot(day_of_week=1, start_time="09:00", end_time="11:00").status_code, 201)

    def test_inactive_market_rejects_new_slot(self):
        fm_closed = FarmerMarket.objects.create(farmer=self.farmer, market=self.market_closed, stall_label="C1")
        res = self._slot(farmer_market_id=fm_closed.pk, day_of_week=1)
        self.assertEqual(res.status_code, 400)
        self.assertIn("farmer_market_id", res.data["errors"])


    def test_update_slot_time_and_turn_off(self):
        url = f"{SLOTS_URL}{self.slot_mon.pk}/"
        res = self.client.patch(url, {"start_time": "08:00", "end_time": "10:00"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["start_time"], "08:00")
        res = self.client.patch(url, {"is_active": False}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data["data"]["is_active"])

    def test_turning_on_rechecks_rules(self):
        PickupSlot.objects.filter(pk=self.slot_mon.pk).update(is_active=False)
        Market.objects.filter(pk=self.market_a.pk).update(open_time="08:00")
        url = f"{SLOTS_URL}{self.slot_mon.pk}/"
        res = self.client.patch(url, {"is_active": True}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("start_time", res.data["errors"])
        res = self.client.patch(url, {"start_time": "08:00", "is_active": True}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["data"]["is_active"])

    def test_slot_that_no_longer_fits_can_still_be_turned_off(self):
        Market.objects.filter(pk=self.market_a.pk).update(open_time="08:00")
        FarmerProfile.objects.filter(pk=self.farmer.pk).update(operating_days=[3, 5])
        res = self.client.patch(f"{SLOTS_URL}{self.slot_mon.pk}/", {"is_active": False}, format="json")
        self.assertEqual(res.status_code, 200)

    def test_update_slot_overlap_and_ownership(self):
        second = PickupSlot.objects.create(farmer_market=self.fm_a, day_of_week=1, start_time="10:00", end_time="11:00")
        res = self.client.patch(f"{SLOTS_URL}{second.pk}/", {"start_time": "08:30"}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("start_time", res.data["errors"])
        res = self.client.patch(f"{SLOTS_URL}{self.other_slot.pk}/", {"is_active": False}, format="json")
        self.assertEqual(res.status_code, 404)


    def test_delete_slot(self):
        order = self._order(market=self.market_a, slot=self.slot_mon)
        url = f"{SLOTS_URL}{self.slot_mon.pk}/"
        res = self.client.delete(url)
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.data["code"], ErrorCode.RESOURCE_IN_USE)
        self.assertEqual(res.data["errors"]["order_ids"], [order.pk])

        Order.objects.filter(pk=order.pk).update(status=OrderStatus.CANCELLED)
        self.assertEqual(self.client.delete(url).status_code, 204)
        self.assertFalse(PickupSlot.objects.filter(pk=self.slot_mon.pk).exists())
        self.assertEqual(self.client.delete(f"{SLOTS_URL}{self.other_slot.pk}/").status_code, 404)
