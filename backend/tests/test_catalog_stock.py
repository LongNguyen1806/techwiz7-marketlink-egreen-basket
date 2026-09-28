from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser, CustomerProfile, FarmerProfile, Role, RoleCode
from catalog.models import Category, Product, Unit
from catalog.services.stock import apply_stock_delta, get_available_stock, get_held_quantities, lock_products
from markets.models import FarmerMarket, Market, PickupSlot
from orders.models import Order, OrderItem, OrderStatus


class CatalogStockTestCase(TestCase):
    def setUp(self):
        customer_role, _ = Role.objects.get_or_create(
            code=RoleCode.CUSTOMER, defaults={"name": "Customer"}
        )
        farmer_role, _ = Role.objects.get_or_create(
            code=RoleCode.FARMER, defaults={"name": "Farmer"}
        )

        self.customer = CustomUser.objects.create(
            email="cust_stock@marketlink.local",
            role=customer_role,
        )
        CustomerProfile.objects.create(
            user=self.customer,
            full_name="Stock User",
            phone="0911777888",
            address="123 Stock Ave",
        )

        self.farmer_user = CustomUser.objects.create(
            email="farmer_stock@marketlink.local",
            role=farmer_role,
        )
        self.farmer = FarmerProfile.objects.create(
            operating_days=[1, 2, 3, 4, 5, 6, 7],
            user=self.farmer_user,
            stall_name="Stock Farm",
            contact_person="Tran Van Stock",
            phone="0988555444",
            address="456 Stock Farm Rd",
            order_cutoff_hours=12,
        )

        self.market = Market.objects.create(
            name="Stock Market",
            address="789 Stock Blvd",
            latitude=Decimal("10.7769"),
            longitude=Decimal("106.7009"),
            open_time="06:00:00",
            close_time="20:00:00",
        )
        self.farmer_market = FarmerMarket.objects.create(
            farmer=self.farmer,
            market=self.market,
            stall_label="Stall S1",
        )

        self.category = Category.objects.create(name="Root Vegetables")
        self.product = Product.objects.create(
            farmer=self.farmer,
            category=self.category,
            name="Carrots",
            unit=Unit.KG,
            price=Decimal("12.00"),
            stock_quantity=50,
        )

        now = timezone.now()
        self.slot = PickupSlot.objects.create(
            farmer_market=self.farmer_market,
            day_of_week=now.date().isoweekday(),
            start_time="14:00:00",
            end_time="16:00:00",
            is_active=True,
        )

    def _create_order_with_status(
        self, status: str, qty: int, start_offset_hours: int = 24
    ) -> Order:
        now = timezone.now()
        start_at = now + timedelta(hours=start_offset_hours)
        end_at = start_at + timedelta(hours=2)
        cutoff_at = now + timedelta(hours=start_offset_hours - 12)

        order = Order.objects.create(
            customer=self.customer,
            farmer=self.farmer,
            market=self.market,
            pickup_slot=self.slot,
            stall_label="Stall S1",
            pickup_date=start_at.date(),
            pickup_start_at=start_at,
            pickup_end_at=end_at,
            cutoff_at=cutoff_at,
            total_amount=self.product.price * qty,
            status=status,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product,
            product_name=self.product.name,
            unit=self.product.unit,
            unit_price=self.product.price,
            quantity=qty,
            line_total=self.product.price * qty,
        )
        return order

    def test_held_quantities_only_counts_active_placed_orders(self):
        self._create_order_with_status(OrderStatus.PLACED, qty=5, start_offset_hours=24)

        self._create_order_with_status(OrderStatus.PLACED, qty=10, start_offset_hours=-2)

        self._create_order_with_status(OrderStatus.ACCEPTED, qty=7, start_offset_hours=24)

        self._create_order_with_status(OrderStatus.CANCELLED, qty=3, start_offset_hours=24)

        held_map = get_held_quantities(product_ids=[self.product.id])
        self.assertEqual(held_map.get(self.product.id, 0), 5)

    def test_available_stock_calculation(self):
        self._create_order_with_status(OrderStatus.PLACED, qty=8, start_offset_hours=24)

        available = get_available_stock(product=self.product)
        self.assertEqual(available, 42)

    def test_apply_stock_delta(self):
        products = lock_products(product_ids=[self.product.id])
        apply_stock_delta(products=products, deltas={self.product.id: -15})

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 35)

        apply_stock_delta(products=products, deltas={self.product.id: 5})
        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, 40)
