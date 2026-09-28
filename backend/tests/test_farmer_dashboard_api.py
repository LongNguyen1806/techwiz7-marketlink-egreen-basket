from datetime import datetime, time, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CustomUser, CustomerProfile, FarmerProfile, FarmerStatus, Role, RoleCode
from catalog.models import Category, Product, Unit
from markets.models import Market
from orders.models import Order, OrderItem, OrderStatus

URL = "/api/farmer/dashboard/"
_S = OrderStatus


class FarmerDashboardAPITestCase(TestCase):
    """F8: FA-01 (F-01, FR-46) with decisions D1-D4 v1.8."""

    def setUp(self):
        self.client = APIClient()
        self.today = timezone.localdate()
        farmer_role, _ = Role.objects.get_or_create(code=RoleCode.FARMER, defaults={"name": "Farmer"})
        customer_role, _ = Role.objects.get_or_create(code=RoleCode.CUSTOMER, defaults={"name": "Customer"})
        self.farmer_user = CustomUser.objects.create(email="dash_farmer@marketlink.local", role=farmer_role)
        self.farmer = FarmerProfile.objects.create(
            user=self.farmer_user,
            stall_name="Dash Stall",
            contact_person="Dash Farmer",
            phone="0955100100",
            address="1 Dash Road",
            status=FarmerStatus.APPROVED,
            operating_days=[1, 2, 3, 4, 5, 6, 7],
        )
        other_user = CustomUser.objects.create(email="dash_other@marketlink.local", role=farmer_role)
        self.other_farmer = FarmerProfile.objects.create(
            user=other_user,
            stall_name="Other Dash",
            contact_person="Other",
            phone="0955100200",
            address="2 Dash Road",
            operating_days=[1],
        )
        self.customer = CustomUser.objects.create(email="dash_customer@marketlink.local", role=customer_role)
        CustomerProfile.objects.create(user=self.customer, full_name="Khach D", phone="0911400100", address="3 Road")
        self.market = Market.objects.create(
            name="Dash Market",
            address="Market address",
            latitude=Decimal("10.770000"),
            longitude=Decimal("106.700000"),
            open_time="05:00",
            close_time="20:00",
        )
        category = Category.objects.create(name="Fruit")
        self.mango = self._product("Mango", category)
        self.lime = self._product("Lime", category)
        self.kale = self._product("Kale", category)
        self.client.force_authenticate(user=self.farmer_user)

    def _product(self, name, category, farmer=None) -> Product:
        return Product.objects.create(
            farmer=farmer or self.farmer, category=category, name=name, unit=Unit.KG, price=Decimal("1.00"), stock_quantity=50
        )

    def _order(self, status, *, day_offset=0, hour=9, items=(), farmer=None) -> Order:
        pickup_date = self.today + timedelta(days=day_offset)
        start_at = timezone.make_aware(datetime.combine(pickup_date, time(hour, 0)), timezone.get_current_timezone())
        total = sum((price * qty for _, qty, price in items), Decimal("0.00"))
        order = Order.objects.create(
            customer=self.customer,
            farmer=farmer or self.farmer,
            market=self.market,
            stall_label="D1",
            pickup_date=pickup_date,
            pickup_start_at=start_at,
            pickup_end_at=start_at + timedelta(hours=2),
            cutoff_at=start_at - timedelta(hours=12),
            total_amount=total,
            status=status,
        )
        for product, qty, price in items:
            OrderItem.objects.create(
                order=order,
                product=product,
                product_name=product.name,
                unit=product.unit,
                unit_price=price,
                quantity=qty,
                line_total=price * qty,
            )
        return order

    def _get(self, **params):
        res = self.client.get(URL, params)
        self.assertEqual(res.status_code, 200, res.data)
        return res.data["data"]

    def test_shape_and_default_range(self):
        data = self._get()
        self.assertEqual(
            set(data),
            {"kpis", "revenue_by_day", "top_products", "overdue_open_count", "upcoming", "status", "status_reason", "range"},
        )
        self.assertEqual(set(data["kpis"]), {"total_orders", "pending_approval", "in_progress", "revenue"})
        self.assertEqual(data["range"], {"from": (self.today - timedelta(days=6)).isoformat(), "to": self.today.isoformat()})
        self.assertEqual(len(data["revenue_by_day"]), 7)
        self.assertTrue(all(row["revenue"] == "0.00" for row in data["revenue_by_day"]))
        self.assertEqual(data["kpis"]["revenue"], "0.00")
        self.assertEqual(data["status"], FarmerStatus.APPROVED)

    def test_range_kpis_follow_pickup_date(self):
        self._order(_S.COMPLETED, day_offset=-1, items=[(self.mango, 2, Decimal("3.00"))])
        self._order(_S.COMPLETED, day_offset=-3, items=[(self.lime, 5, Decimal("1.00"))])
        self._order(_S.CANCELLED, day_offset=-2, items=[(self.mango, 9, Decimal("3.00"))])
        self._order(_S.COMPLETED, day_offset=-10, items=[(self.kale, 1, Decimal("50.00"))])
        self._order(_S.COMPLETED, day_offset=-1, items=[(self.mango, 1, Decimal("99.00"))], farmer=self.other_farmer)

        data = self._get()
        self.assertEqual(data["kpis"]["total_orders"], 3)
        self.assertEqual(data["kpis"]["revenue"], "11.00")
        by_day = {row["date"]: row["revenue"] for row in data["revenue_by_day"]}
        self.assertEqual(by_day[(self.today - timedelta(days=1)).isoformat()], "6.00")
        self.assertEqual(by_day[(self.today - timedelta(days=3)).isoformat()], "5.00")
        self.assertEqual(by_day[(self.today - timedelta(days=2)).isoformat()], "0.00")

        wide = self._get(**{"from": (self.today - timedelta(days=30)).isoformat()})
        self.assertEqual(wide["kpis"]["revenue"], "61.00")
        self.assertEqual(len(wide["revenue_by_day"]), 31)

    def test_top_products_by_quantity_from_completed_orders(self):
        self._order(_S.COMPLETED, day_offset=-1, items=[(self.mango, 2, Decimal("3.00")), (self.lime, 5, Decimal("1.00"))])
        self._order(_S.COMPLETED, day_offset=-2, items=[(self.mango, 4, Decimal("3.00"))])
        self._order(_S.CANCELLED, day_offset=-1, items=[(self.kale, 100, Decimal("1.00"))])
        Product.objects.filter(pk=self.mango.pk).update(name="Mango (Cat Chu)")

        top = self._get()["top_products"]
        self.assertEqual(
            top,
            [
                {"product_id": self.mango.pk, "name": "Mango (Cat Chu)", "quantity_sold": 6, "revenue": "18.00"},
                {"product_id": self.lime.pk, "name": "Lime", "quantity_sold": 5, "revenue": "5.00"},
            ],
        )

    def test_top_products_limited_to_five(self):
        category = Category.objects.create(name="Veg")
        items = [(self._product(f"P{i}", category), i + 1, Decimal("1.00")) for i in range(7)]
        self._order(_S.COMPLETED, day_offset=-1, items=items)
        top = self._get()["top_products"]
        self.assertEqual([row["name"] for row in top], ["P6", "P5", "P4", "P3", "P2"])

    def test_current_state_kpis_ignore_range(self):
        self._order(_S.PLACED, day_offset=20, items=[(self.mango, 1, Decimal("1.00"))])
        self._order(_S.PLACED, day_offset=2, items=[(self.mango, 1, Decimal("1.00"))])
        self._order(_S.ACCEPTED, day_offset=15, items=[(self.mango, 1, Decimal("1.00"))])
        self._order(_S.READY_FOR_PICKUP, day_offset=1, items=[(self.mango, 1, Decimal("1.00"))])
        data = self._get(**{"from": self.today.isoformat(), "to": self.today.isoformat()})
        self.assertEqual(data["kpis"]["pending_approval"], 2)
        self.assertEqual(data["kpis"]["in_progress"], 2)
        self.assertEqual(data["kpis"]["total_orders"], 0)

    def test_overdue_open_count(self):
        self._order(_S.ACCEPTED, day_offset=-2, items=[(self.mango, 1, Decimal("1.00"))])
        self._order(_S.READY_FOR_PICKUP, day_offset=-1, items=[(self.mango, 1, Decimal("1.00"))])
        self._order(_S.ACCEPTED, day_offset=3, items=[(self.mango, 1, Decimal("1.00"))])
        self._order(_S.COMPLETED, day_offset=-1, items=[(self.mango, 1, Decimal("1.00"))])
        self.assertEqual(self._get()["overdue_open_count"], 2)

    def test_upcoming_open_orders_nearest_first(self):
        far = self._order(_S.ACCEPTED, day_offset=6, items=[(self.mango, 1, Decimal("1.00"))])
        near = self._order(_S.PLACED, day_offset=1, items=[(self.mango, 1, Decimal("1.00"))])
        mid = self._order(_S.READY_FOR_PICKUP, day_offset=3, items=[(self.mango, 1, Decimal("1.00"))])
        self._order(_S.ACCEPTED, day_offset=-1, items=[(self.mango, 1, Decimal("1.00"))])
        self._order(_S.CANCELLED, day_offset=1, items=[(self.mango, 1, Decimal("1.00"))])
        for day in range(7, 11):
            self._order(_S.ACCEPTED, day_offset=day, items=[(self.mango, 1, Decimal("1.00"))])

        upcoming = self._get()["upcoming"]
        self.assertEqual(len(upcoming), 5)
        self.assertEqual([row["id"] for row in upcoming[:3]], [near.pk, mid.pk, far.pk])
        self.assertIn("customer", upcoming[0])
        self.assertIn("version", upcoming[0])

    def test_lazy_sweep_runs_first(self):
        overdue = self._order(_S.PLACED, day_offset=-1, items=[(self.mango, 1, Decimal("1.00"))])
        data = self._get()
        overdue.refresh_from_db()
        self.assertEqual(overdue.status, _S.EXPIRED)
        self.assertEqual(data["kpis"]["pending_approval"], 0)

    def test_status_banner(self):
        FarmerProfile.objects.filter(pk=self.farmer.pk).update(status=FarmerStatus.SUSPENDED, status_reason="Late deliveries")
        data = self._get()
        self.assertEqual((data["status"], data["status_reason"]), (FarmerStatus.SUSPENDED, "Late deliveries"))

    def test_invalid_ranges(self):
        cases = [
            {"from": "2026-02-30"},
            {"to": "yesterday"},
            {"from": self.today.isoformat(), "to": (self.today - timedelta(days=1)).isoformat()},
            {"from": (self.today - timedelta(days=366)).isoformat(), "to": self.today.isoformat()},
        ]
        for params in cases:
            with self.subTest(params=params):
                res = self.client.get(URL, params)
                self.assertEqual(res.status_code, 400)
        ok = self.client.get(URL, {"from": (self.today - timedelta(days=365)).isoformat()})
        self.assertEqual(ok.status_code, 200)

    def test_customer_is_forbidden(self):
        self.client.force_authenticate(user=self.customer)
        self.assertEqual(self.client.get(URL).status_code, 403)
