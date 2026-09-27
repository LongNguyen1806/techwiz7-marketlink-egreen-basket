from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser, CustomerProfile, FarmerProfile, Role, RoleCode
from catalog.models import Category, Product, ReviewStatus, Unit
from marketlink_core.exceptions import (
    BusinessValidationError,
    ConflictError,
    ErrorCode,
    ForbiddenActionError,
    UnprocessableEntityError,
)
from markets.models import FarmerMarket, Market, PickupSlot
from orders.models import ActorRole, Order, OrderItem, OrderStatus, Transition
from orders.services.fsm import record_order_placed, transition_order
from orders.services.modify import modify_order


class OrderModifyTestCase(TestCase):
    def setUp(self):
        customer_role, _ = Role.objects.get_or_create(
            code=RoleCode.CUSTOMER, defaults={"name": "Customer"}
        )
        farmer_role, _ = Role.objects.get_or_create(
            code=RoleCode.FARMER, defaults={"name": "Farmer"}
        )

        self.customer = CustomUser.objects.create(
            email="cust_modify@marketlink.local",
            role=customer_role,
        )
        CustomerProfile.objects.create(
            user=self.customer,
            full_name="Nguyen Van Mod",
            phone="0911333444",
            address="789 Mod Street",
        )

        self.other_customer = CustomUser.objects.create(
            email="other_cust@marketlink.local",
            role=customer_role,
        )

        self.farmer_user = CustomUser.objects.create(
            email="farmer_modify@marketlink.local",
            role=farmer_role,
        )
        self.farmer = FarmerProfile.objects.create(
            operating_days=[1, 2, 3, 4, 5, 6, 7],
            user=self.farmer_user,
            stall_name="Modify Garden",
            contact_person="Tran Van Mod",
            phone="0988666555",
            address="321 Farm Mod Road",
            order_cutoff_hours=12,
        )

        self.market = Market.objects.create(
            name="Central Modify Market",
            address="123 Mod Blvd",
            latitude=Decimal("10.7769"),
            longitude=Decimal("106.7009"),
            open_time="06:00:00",
            close_time="20:00:00",
        )
        self.farmer_market = FarmerMarket.objects.create(
            farmer=self.farmer,
            market=self.market,
            stall_label="Stall M1",
        )

        self.category = Category.objects.create(name="Greens")
        self.product1 = Product.objects.create(
            review_status=ReviewStatus.APPROVED,
            farmer=self.farmer,
            category=self.category,
            name="Organic Spinach",
            unit=Unit.KG,
            price=Decimal("10.00"),
            stock_quantity=50,
        )
        self.product2 = Product.objects.create(
            review_status=ReviewStatus.APPROVED,
            farmer=self.farmer,
            category=self.category,
            name="Fresh Mint",
            unit=Unit.BUNCH,
            price=Decimal("5.00"),
            stock_quantity=30,
        )

        now = timezone.now()
        self.pickup_date = (now + timedelta(days=2)).date()
        self.slot = PickupSlot.objects.create(
            farmer_market=self.farmer_market,
            day_of_week=self.pickup_date.isoweekday(),
            start_time="14:00:00",
            end_time="16:00:00",
            is_active=True,
        )

    def _create_order(
        self, start_in_hours: int = 48, cutoff_in_hours: int = 36, qty: int = 2
    ) -> Order:
        now = timezone.now()
        start_at = now + timedelta(hours=start_in_hours)
        end_at = start_at + timedelta(hours=2)
        cutoff_at = now + timedelta(hours=cutoff_in_hours)

        order = Order.objects.create(
            customer=self.customer,
            farmer=self.farmer,
            market=self.market,
            pickup_slot=self.slot,
            stall_label="Stall M1",
            pickup_date=start_at.date(),
            pickup_start_at=start_at,
            pickup_end_at=end_at,
            cutoff_at=cutoff_at,
            total_amount=self.product1.price * qty,
            status=OrderStatus.PLACED,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product1,
            product_name=self.product1.name,
            unit=self.product1.unit,
            unit_price=self.product1.price,
            quantity=qty,
            line_total=self.product1.price * qty,
        )
        record_order_placed(order=order, actor=self.customer)
        return order

    def test_modify_accepted_order_creates_pending_change_without_modifying_status_or_stock(self):
        order = self._create_order(qty=2)

        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.ACCEPTED,
            actor=self.farmer_user,
            actor_role=ActorRole.FARMER,
            expected_version=order.version,
        )
        self.assertEqual(order.status, OrderStatus.ACCEPTED)
        stock_before_modify = Product.objects.get(id=self.product1.id).stock_quantity

        # Customer submits modification for an ACCEPTED order
        modified = modify_order(
            order_id=order.id,
            actor=self.customer,
            expected_version=order.version,
            items_data=[{"product_id": self.product1.id, "quantity": 6}],
            note="Fresh please",
        )

        # Under D-030 v1.7, status stays ACCEPTED and items are kept intact
        self.assertEqual(modified.status, OrderStatus.ACCEPTED)
        self.assertEqual(modified.version, 3)

        # Physical stock is NOT modified yet
        stock_after_modify = Product.objects.get(id=self.product1.id).stock_quantity
        self.assertEqual(stock_after_modify, stock_before_modify)

        # Order items in DB remain unchanged (qty 2)
        self.assertEqual(modified.items.first().quantity, 2)
        self.assertEqual(modified.total_amount, Decimal("20.00"))

        # pending_change is recorded
        self.assertIsNotNone(modified.pending_change)
        self.assertEqual(modified.pending_change["items"][0]["quantity"], 6)

        # History is recorded with transition=None, from_status=ACCEPTED, to_status=ACCEPTED
        latest_history = modified.status_history.last()
        self.assertIsNone(latest_history.transition)
        self.assertEqual(latest_history.from_status, OrderStatus.ACCEPTED)
        self.assertEqual(latest_history.to_status, OrderStatus.ACCEPTED)
        self.assertEqual(latest_history.actor_role, ActorRole.CUSTOMER)
        self.assertTrue(latest_history.change_reason.startswith("Change request submitted:"))

    def test_modify_placed_order_stays_placed_and_does_not_modify_physical_stock(self):
        order = self._create_order(qty=2)
        stock_before = Product.objects.get(id=self.product1.id).stock_quantity

        # Modify item quantity while still PLACED
        modified = modify_order(
            order_id=order.id,
            actor=self.customer,
            expected_version=order.version,
            items_data=[{"product_id": self.product1.id, "quantity": 5}],
        )

        self.assertEqual(modified.status, OrderStatus.PLACED)
        # PLACED orders do not adjust physical stock
        self.assertEqual(Product.objects.get(id=self.product1.id).stock_quantity, stock_before)
        self.assertEqual(modified.total_amount, Decimal("50.00"))

        latest_history = modified.status_history.last()
        self.assertIsNone(latest_history.transition)
        self.assertEqual(latest_history.from_status, OrderStatus.PLACED)
        self.assertEqual(latest_history.to_status, OrderStatus.PLACED)

    def test_modify_order_preserves_snapshot_unit_price(self):
        order = self._create_order(qty=2)
        self.assertEqual(order.items.first().unit_price, Decimal("10.00"))

        # Catalog price surges to $25 after order was placed
        self.product1.price = Decimal("25.00")
        self.product1.save()

        # Customer adds a new product while keeping product1
        modified = modify_order(
            order_id=order.id,
            actor=self.customer,
            expected_version=order.version,
            items_data=[
                {"product_id": self.product1.id, "quantity": 2},
                {"product_id": self.product2.id, "quantity": 3},
            ],
        )

        item1 = modified.items.get(product_id=self.product1.id)
        item2 = modified.items.get(product_id=self.product2.id)

        # Existing item preserves original snapshot price $10.00
        self.assertEqual(item1.unit_price, Decimal("10.00"))
        self.assertEqual(item1.line_total, Decimal("20.00"))

        # New item gets current catalog price $5.00
        self.assertEqual(item2.unit_price, Decimal("5.00"))
        self.assertEqual(item2.line_total, Decimal("15.00"))
        self.assertEqual(modified.total_amount, Decimal("35.00"))

    def test_modify_order_after_cutoff_fails(self):
        order = self._create_order(start_in_hours=10, cutoff_in_hours=-1, qty=2)

        with self.assertRaises(UnprocessableEntityError) as ctx:
            modify_order(
                order_id=order.id,
                actor=self.customer,
                expected_version=order.version,
                items_data=[{"product_id": self.product1.id, "quantity": 4}],
            )
        self.assertEqual(ctx.exception.code, ErrorCode.CUTOFF_PASSED)

    def test_modify_order_stale_version_fails_occ(self):
        order = self._create_order(qty=2)

        with self.assertRaises(ConflictError) as ctx:
            modify_order(
                order_id=order.id,
                actor=self.customer,
                expected_version=999,
                note="New note",
            )
        self.assertEqual(ctx.exception.code, ErrorCode.RESOURCE_MODIFIED)

    def test_modify_order_forbidden_for_non_owner(self):
        order = self._create_order(qty=2)

        with self.assertRaises(ForbiddenActionError) as ctx:
            modify_order(
                order_id=order.id,
                actor=self.other_customer,
                expected_version=order.version,
                note="Unauthorized change",
            )
        self.assertEqual(ctx.exception.code, ErrorCode.ACTION_NOT_PERMITTED_FOR_ROLE)

    def test_modify_order_empty_items_fails(self):
        order = self._create_order(qty=2)

        with self.assertRaises(BusinessValidationError) as ctx:
            modify_order(
                order_id=order.id,
                actor=self.customer,
                expected_version=order.version,
                items_data=[],
            )
        self.assertEqual(ctx.exception.code, ErrorCode.VALIDATION_ERROR)

    def test_modify_cannot_raise_a_line_above_the_stall_cap(self):
        self.product1.max_per_order = 3
        self.product1.save(update_fields=["max_per_order"])
        order = self._create_order(qty=2)

        with self.assertRaises(BusinessValidationError) as ctx:
            modify_order(
                order_id=order.id,
                actor=self.customer,
                expected_version=order.version,
                items_data=[{"product_id": self.product1.id, "quantity": 4}],
            )
        self.assertEqual(ctx.exception.code, ErrorCode.VALIDATION_ERROR)

        modified = modify_order(
            order_id=order.id,
            actor=self.customer,
            expected_version=order.version,
            items_data=[{"product_id": self.product1.id, "quantity": 3}],
        )
        self.assertEqual(modified.items.get().quantity, 3)

    def test_a_line_of_a_listing_in_review_can_be_lowered_but_not_raised(self):
        order = self._create_order(qty=2)
        self.product1.review_status = ReviewStatus.PENDING
        self.product1.save(update_fields=["review_status"])

        with self.assertRaises(UnprocessableEntityError) as ctx:
            modify_order(
                order_id=order.id,
                actor=self.customer,
                expected_version=order.version,
                items_data=[{"product_id": self.product1.id, "quantity": 3}],
            )
        self.assertEqual(ctx.exception.code, ErrorCode.PRODUCT_NOT_AVAILABLE)

        modified = modify_order(
            order_id=order.id,
            actor=self.customer,
            expected_version=order.version,
            items_data=[{"product_id": self.product1.id, "quantity": 1}],
        )
        self.assertEqual(modified.items.get().quantity, 1)

    def test_a_changed_line_must_meet_the_stall_minimum_but_an_untouched_one_may_stay_below(self):
        order = self._create_order(qty=2)
        self.product1.min_per_order = 3
        self.product1.save(update_fields=["min_per_order"])

        # Unchanged line: the minimum rose after the order was placed, which is not the customer's doing.
        kept = modify_order(
            order_id=order.id,
            actor=self.customer,
            expected_version=order.version,
            items_data=[{"product_id": self.product1.id, "quantity": 2}],
        )
        self.assertEqual(kept.items.get().quantity, 2)

        with self.assertRaises(BusinessValidationError) as ctx:
            modify_order(
                order_id=order.id,
                actor=self.customer,
                expected_version=kept.version,
                items_data=[{"product_id": self.product1.id, "quantity": 1}],
            )
        self.assertEqual(ctx.exception.code, ErrorCode.VALIDATION_ERROR)
