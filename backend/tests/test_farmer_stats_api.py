from datetime import datetime, time, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CustomUser, CustomerProfile, FarmerProfile, FarmerStatus, Role, RoleCode
from catalog.models import Category, Product, Unit
from markets.models import Market
from orders.models import Order, OrderItem, OrderStatus
from reviews.models import FarmerReview, ProductReview

URL = "/api/farmer/dashboard/stats/"
_S = OrderStatus


class FarmerStatsAPITestCase(TestCase):
    """FA-01b: the Stats page; every figure follows the pickup_date range."""

    def setUp(self):
        self.client = APIClient()
        self.today = timezone.localdate()
        farmer_role, _ = Role.objects.get_or_create(code=RoleCode.FARMER, defaults={"name": "Farmer"})
        customer_role, _ = Role.objects.get_or_create(code=RoleCode.CUSTOMER, defaults={"name": "Customer"})
        self.farmer_user = CustomUser.objects.create(email="stats_farmer@marketlink.local", role=farmer_role)
        self.farmer = FarmerProfile.objects.create(
            user=self.farmer_user,
            stall_name="Stats Stall",
            contact_person="Stats Farmer",
            phone="0955300100",
            address="1 Stats Road",
            status=FarmerStatus.APPROVED,
            operating_days=[1, 2, 3, 4, 5, 6, 7],
        )
        other_user = CustomUser.objects.create(email="stats_other@marketlink.local", role=farmer_role)
        self.other_farmer = FarmerProfile.objects.create(
            user=other_user,
            stall_name="Other Stats",
            contact_person="Other",
            phone="0955300200",
            address="2 Stats Road",
            operating_days=[1],
        )
        self.anna = self._customer("stats_anna@marketlink.local", "Anna", "0911500100")
        self.binh = self._customer("stats_binh@marketlink.local", "Binh", "0911500200")
        self.north = self._market("North Market")
        self.south = self._market("South Market")
        category = Category.objects.create(name="Fruit")
        self.mango = Product.objects.create(
            farmer=self.farmer, category=category, name="Mango", unit=Unit.KG, price=Decimal("3.00"), stock_quantity=50
        )
        self.lime = Product.objects.create(
            farmer=self.farmer, category=category, name="Lime", unit=Unit.BUNCH, price=Decimal("1.00"), stock_quantity=50
        )
        self.client.force_authenticate(user=self.farmer_user)

    def _customer(self, email, name, phone):
        role = Role.objects.get(code=RoleCode.CUSTOMER)
        user = CustomUser.objects.create(email=email, role=role)
        CustomerProfile.objects.create(user=user, full_name=name, phone=phone, address="Road")
        return user

    def _market(self, name):
        return Market.objects.create(
            name=name,
            address=f"{name} address",
            latitude=Decimal("10.770000"),
            longitude=Decimal("106.700000"),
            open_time="05:00",
            close_time="20:00",
        )

    def _order(self, status, *, day_offset=-1, customer=None, market=None, items=(), farmer=None):
        pickup_date = self.today + timedelta(days=day_offset)
        start_at = timezone.make_aware(datetime.combine(pickup_date, time(9, 0)), timezone.get_current_timezone())
        order = Order.objects.create(
            customer=customer or self.anna,
            farmer=farmer or self.farmer,
            market=market or self.north,
            stall_label="S1",
            pickup_date=pickup_date,
            pickup_start_at=start_at,
            pickup_end_at=start_at + timedelta(hours=2),
            cutoff_at=start_at - timedelta(hours=12),
            total_amount=sum((price * qty for _, qty, price in items), Decimal("0.00")),
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

    def test_kpis_follow_the_range_and_compare_with_the_period_before(self):
        self._order(_S.COMPLETED, day_offset=-1, items=[(self.mango, 2, Decimal("3.00"))])
        self._order(_S.COMPLETED, day_offset=-2, items=[(self.lime, 4, Decimal("1.00"))])
        self._order(_S.COMPLETED, day_offset=-3, customer=self.binh, items=[(self.mango, 1, Decimal("5.00"))])
        self._order(_S.CANCELLED, day_offset=-2, items=[(self.mango, 9, Decimal("3.00"))])
        self._order(_S.PLACED, day_offset=0, items=[(self.lime, 1, Decimal("1.00"))])
        self._order(_S.COMPLETED, day_offset=-9, items=[(self.mango, 1, Decimal("8.00"))])
        self._order(_S.COMPLETED, day_offset=-1, items=[(self.mango, 1, Decimal("99.00"))], farmer=self.other_farmer)

        data = self._get()
        kpis = data["kpis"]
        self.assertEqual(data["previous_range"]["to"], (self.today - timedelta(days=7)).isoformat())
        self.assertEqual(kpis["revenue"], "15.00")
        self.assertEqual(kpis["previous_revenue"], "8.00")
        self.assertEqual(kpis["total_orders"], 5)
        self.assertEqual(kpis["completed_orders"], 3)
        self.assertEqual(kpis["finished_orders"], 4)
        self.assertEqual(kpis["average_order_value"], "5.00")
        self.assertEqual(kpis["customers"], 2)
        self.assertEqual(kpis["returning_customers"], 1)
        self.assertEqual(data["open_orders"], 1)
        self.assertNotIn("pending_approval", kpis)

    def test_breakdowns_by_status_product_market_and_weekday(self):
        self._order(_S.COMPLETED, day_offset=-1, items=[(self.mango, 2, Decimal("3.00")), (self.lime, 3, Decimal("1.00"))])
        self._order(_S.COMPLETED, day_offset=-1, market=self.south, items=[(self.mango, 1, Decimal("3.00"))])
        self._order(_S.NO_SHOW, day_offset=-2, items=[(self.lime, 1, Decimal("1.00"))])
        self._order(_S.DECLINED, day_offset=-2, items=[(self.lime, 1, Decimal("1.00"))])

        data = self._get()
        statuses = {row["status"]: row["count"] for row in data["orders_by_status"]}
        self.assertEqual(statuses, {"COMPLETED": 2, "CANCELLED": 0, "DECLINED": 1, "NO_SHOW": 1, "EXPIRED": 0})

        mango, lime = data["top_products"]
        self.assertEqual((mango["name"], mango["unit"], mango["quantity_sold"], mango["orders"], mango["revenue"]),
                         ("Mango", Unit.KG, 3, 2, "9.00"))
        self.assertEqual((lime["name"], lime["quantity_sold"], lime["revenue"]), ("Lime", 3, "3.00"))

        markets = [(row["name"], row["revenue"], row["orders"]) for row in data["sales_by_market"]]
        self.assertEqual(markets, [("North Market", "9.00", 1), ("South Market", "3.00", 1)])

        yesterday = (self.today - timedelta(days=1)).isoweekday()
        weekdays = {row["weekday"]: row["orders"] for row in data["orders_by_weekday"]}
        self.assertEqual(len(weekdays), 7)
        self.assertEqual(weekdays[yesterday], 2)

        day = next(row for row in data["revenue_by_day"] if row["date"] == (self.today - timedelta(days=1)).isoformat())
        self.assertEqual((day["revenue"], day["orders"]), ("12.00", 2))

    def test_rating_leaves_out_reviews_hidden_by_the_admin(self):
        first = self._order(_S.COMPLETED, items=[(self.mango, 1, Decimal("3.00"))])
        second = self._order(_S.COMPLETED, customer=self.binh, items=[(self.lime, 1, Decimal("1.00"))])
        FarmerReview.objects.create(order=first, rating=5)
        ProductReview.objects.create(order_item=first.items.get(), rating=4)
        FarmerReview.objects.create(order=second, rating=1, is_hidden_by_admin=True)

        rating = self._get()["kpis"]["rating"]
        self.assertEqual(rating, {"average": 4.5, "count": 2})

    def test_empty_range_has_no_averages(self):
        data = self._get(**{"from": (self.today - timedelta(days=29)).isoformat(), "to": self.today.isoformat()})
        self.assertEqual(len(data["revenue_by_day"]), 30)
        self.assertEqual(data["kpis"]["average_order_value"], "0.00")
        self.assertEqual(data["kpis"]["rating"], {"average": None, "count": 0})
        self.assertEqual(data["top_products"], [])
