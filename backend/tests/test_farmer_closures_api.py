from datetime import datetime, time, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CustomUser, CustomerProfile, FarmerProfile, FarmerStatus, Role, RoleCode
from marketlink_core.exceptions import ErrorCode
from markets.models import FarmerClosure, Market
from orders.models import Order, OrderStatus

URL = "/api/farmer/closures/"


class FarmerClosuresAPITestCase(TestCase):
    """F3: FA-31 -> FA-33 (D-023)."""

    def setUp(self):
        self.client = APIClient()
        self.today = timezone.localdate()
        farmer_role, _ = Role.objects.get_or_create(code=RoleCode.FARMER, defaults={"name": "Farmer"})
        customer_role, _ = Role.objects.get_or_create(code=RoleCode.CUSTOMER, defaults={"name": "Customer"})
        self.farmer_user = CustomUser.objects.create(email="closure_farmer@marketlink.local", role=farmer_role)
        self.farmer = FarmerProfile.objects.create(
            user=self.farmer_user,
            stall_name="Closure Stall",
            contact_person="Pham Van C",
            phone="0966100100",
            address="1 Closure Road",
            status=FarmerStatus.APPROVED,
            operating_days=[1, 2, 3, 4, 5, 6, 7],
        )
        other_user = CustomUser.objects.create(email="closure_other@marketlink.local", role=farmer_role)
        self.other_farmer = FarmerProfile.objects.create(
            user=other_user,
            stall_name="Other Closure",
            contact_person="Vo Van O",
            phone="0966100200",
            address="2 Closure Road",
            operating_days=[1],
        )
        self.customer = CustomUser.objects.create(email="closure_customer@marketlink.local", role=customer_role)
        CustomerProfile.objects.create(user=self.customer, full_name="Khach C", phone="0911200100", address="3 Road")
        self.market = Market.objects.create(
            name="Closure Market",
            address="Market address",
            latitude=Decimal("10.770000"),
            longitude=Decimal("106.700000"),
            open_time="06:00",
            close_time="12:00",
        )
        self.client.force_authenticate(user=self.farmer_user)

    def _days(self, offset: int) -> str:
        return (self.today + timedelta(days=offset)).isoformat()

    def _order(self, days_ahead: int, status=OrderStatus.PLACED) -> Order:
        pickup_date = self.today + timedelta(days=days_ahead)
        start_at = timezone.make_aware(datetime.combine(pickup_date, time(7, 0)), timezone.get_current_timezone())
        return Order.objects.create(
            customer=self.customer,
            farmer=self.farmer,
            market=self.market,
            stall_label="C1",
            pickup_date=pickup_date,
            pickup_start_at=start_at,
            pickup_end_at=start_at + timedelta(hours=2),
            cutoff_at=start_at - timedelta(hours=12),
            total_amount=Decimal("3.00"),
            status=status,
        )

    def _closure(self, start_offset: int, end_offset: int, farmer=None) -> FarmerClosure:
        return FarmerClosure.objects.create(
            farmer=farmer or self.farmer,
            start_date=self.today + timedelta(days=start_offset),
            end_date=self.today + timedelta(days=end_offset),
        )


    def test_list_hides_past_unless_requested(self):
        self._closure(-10, -8)
        current = self._closure(-1, 1)
        future = self._closure(5, 6)
        self._closure(2, 3, farmer=self.other_farmer)

        res = self.client.get(URL)
        self.assertEqual(res.status_code, 200)
        self.assertEqual([item["id"] for item in res.data["data"]], [current.pk, future.pk])
        self.assertEqual(set(res.data["data"][0]), {"id", "start_date", "end_date", "reason"})

        res = self.client.get(URL, {"include_past": "true"})
        self.assertEqual(len(res.data["data"]), 3)
        self.assertEqual(self.client.get(URL, {"include_past": "maybe"}).status_code, 400)


    def test_create_closure(self):
        res = self.client.post(URL, {"start_date": self._days(3), "end_date": self._days(5), "reason": "  "}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertIsNone(res.data["data"]["reason"])
        self.assertTrue(FarmerClosure.objects.filter(farmer=self.farmer, pk=res.data["data"]["id"]).exists())

    def test_single_day_starting_today_is_allowed(self):
        res = self.client.post(URL, {"start_date": self._days(0), "end_date": self._days(0), "reason": "Family event"}, format="json")
        self.assertEqual(res.status_code, 201)
        self.assertEqual(res.data["data"]["reason"], "Family event")

    def test_create_closure_invalid_dates(self):
        cases = [
            ({"start_date": self._days(-1), "end_date": self._days(2)}, "start_date"),
            ({"start_date": self._days(4), "end_date": self._days(3)}, "end_date"),
            ({"start_date": "2026-13-01", "end_date": self._days(3)}, "start_date"),
            ({"start_date": self._days(1), "end_date": self._days(2), "reason": "x" * 201}, "reason"),
        ]
        for body, field in cases:
            with self.subTest(body=body):
                res = self.client.post(URL, body, format="json")
                self.assertEqual(res.status_code, 400)
                self.assertIn(field, res.data["errors"])

    def test_create_closure_overlap(self):
        self._closure(3, 5)
        self._closure(3, 5, farmer=self.other_farmer)
        res = self.client.post(URL, {"start_date": self._days(5), "end_date": self._days(8)}, format="json")
        self.assertEqual(res.status_code, 400)
        self.assertIn("start_date", res.data["errors"])
        res = self.client.post(URL, {"start_date": self._days(6), "end_date": self._days(8)}, format="json")
        self.assertEqual(res.status_code, 201)

    def test_create_closure_blocked_by_open_orders(self):
        inside = self._order(4)
        self._order(4, OrderStatus.CANCELLED)
        self._order(9)
        res = self.client.post(URL, {"start_date": self._days(3), "end_date": self._days(5)}, format="json")
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.data["code"], ErrorCode.RESOURCE_IN_USE)
        self.assertEqual(res.data["errors"]["order_ids"], [inside.pk])
        self.assertFalse(FarmerClosure.objects.filter(farmer=self.farmer).exists())

    def test_suspended_farmer_can_add_time_off(self):
        FarmerProfile.objects.filter(pk=self.farmer.pk).update(status=FarmerStatus.SUSPENDED)
        res = self.client.post(URL, {"start_date": self._days(1), "end_date": self._days(2)}, format="json")
        self.assertEqual(res.status_code, 201)


    def test_delete_closure(self):
        mine = self._closure(3, 4)
        theirs = self._closure(3, 4, farmer=self.other_farmer)
        self.assertEqual(self.client.delete(f"{URL}{theirs.pk}/").status_code, 404)
        self.assertEqual(self.client.delete(f"{URL}{mine.pk}/").status_code, 204)
        self.assertFalse(FarmerClosure.objects.filter(pk=mine.pk).exists())
        self.assertTrue(FarmerClosure.objects.filter(pk=theirs.pk).exists())
