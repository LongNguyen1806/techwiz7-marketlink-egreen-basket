from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser, CustomerProfile, FarmerProfile, Role, RoleCode
from catalog.models import Category, Product, Unit
from marketlink_core.exceptions import (
    BusinessValidationError,
    ConflictError,
    ErrorCode,
    ForbiddenActionError,
    UnprocessableEntityError,
)
from markets.models import FarmerMarket, Market, PickupSlot
from notifications.models import Notification, NotificationType
from orders.models import ActorRole, ChangeReason, Order, OrderItem, OrderStatus, Transition
from orders.services.expiry import expire_overdue_orders
from orders.services.fsm import record_order_placed, transition_order


class OrderFSMTestCase(TestCase):
    def setUp(self):
        customer_role, _ = Role.objects.get_or_create(
            code=RoleCode.CUSTOMER, defaults={"name": "Customer"}
        )
        farmer_role, _ = Role.objects.get_or_create(
            code=RoleCode.FARMER, defaults={"name": "Farmer"}
        )
        admin_role, _ = Role.objects.get_or_create(
            code=RoleCode.ADMIN, defaults={"name": "Administrator"}
        )

        self.customer = CustomUser.objects.create(
            email="cust_test@marketlink.local",
            role=customer_role,
        )
        CustomerProfile.objects.create(
            user=self.customer,
            full_name="Nguyen Van A",
            phone="0911222333",
            address="123 Test Street",
        )

        self.farmer_user = CustomUser.objects.create(
            email="farmer_test@marketlink.local",
            role=farmer_role,
        )
        self.farmer = FarmerProfile.objects.create(
            operating_days=[1, 2, 3, 4, 5, 6, 7],
            user=self.farmer_user,
            stall_name="Green Garden",
            contact_person="Tran Van B",
            phone="0988777666",
            address="456 Farm Road",
            order_cutoff_hours=12,
        )

        self.admin_user = CustomUser.objects.create(
            email="admin_test@marketlink.local",
            role=admin_role,
        )

        self.market = Market.objects.create(
            name="Test Central Market",
            address="789 Market Blvd",
            latitude=Decimal("10.7769"),
            longitude=Decimal("106.7009"),
            open_time="06:00:00",
            close_time="20:00:00",
        )
        self.farmer_market = FarmerMarket.objects.create(
            farmer=self.farmer,
            market=self.market,
            stall_label="Stall A1",
        )

        self.category = Category.objects.create(name="Vegetables")
        self.product = Product.objects.create(
            farmer=self.farmer,
            category=self.category,
            name="Organic Cabbage",
            unit=Unit.KG,
            price=Decimal("15.00"),
            stock_quantity=50,
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

    def _create_order(self, start_in_hours: int, cutoff_in_hours: int, qty: int = 2) -> Order:
        now = timezone.now()
        start_at = now + timedelta(hours=start_in_hours)
        end_at = start_at + timedelta(hours=2)
        cutoff_at = now + timedelta(hours=cutoff_in_hours)

        order = Order.objects.create(
            customer=self.customer,
            farmer=self.farmer,
            market=self.market,
            pickup_slot=self.slot,
            stall_label="Stall A1",
            pickup_date=start_at.date(),
            pickup_start_at=start_at,
            pickup_end_at=end_at,
            cutoff_at=cutoff_at,
            total_amount=self.product.price * qty,
            status=OrderStatus.PLACED,
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
        record_order_placed(order=order, actor=self.customer)
        return order

    def test_lifecycle_placed_to_completed(self):
        order = self._create_order(start_in_hours=24, cutoff_in_hours=-1, qty=2)
        initial_stock = Product.objects.get(id=self.product.id).stock_quantity

        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.ACCEPTED,
            actor=self.farmer_user,
            actor_role=ActorRole.FARMER,
            expected_version=order.version,
        )
        self.assertEqual(order.status, OrderStatus.ACCEPTED)
        self.assertEqual(Product.objects.get(id=self.product.id).stock_quantity, initial_stock - 2)

        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.READY_FOR_PICKUP,
            actor=self.farmer_user,
            actor_role=ActorRole.FARMER,
            expected_version=order.version,
        )
        self.assertEqual(order.status, OrderStatus.READY_FOR_PICKUP)

        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.COMPLETED,
            actor=self.farmer_user,
            actor_role=ActorRole.FARMER,
            expected_version=order.version,
        )
        self.assertEqual(order.status, OrderStatus.COMPLETED)
        self.assertEqual(order.version, 4)

    def test_farmer_accept_order_deducts_physical_stock(self):
        initial_stock = Product.objects.get(id=self.product.id).stock_quantity
        order = self._create_order(start_in_hours=24, cutoff_in_hours=12, qty=5)

        self.assertEqual(Product.objects.get(id=self.product.id).stock_quantity, initial_stock)

        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.ACCEPTED,
            actor=self.farmer_user,
            actor_role=ActorRole.FARMER,
            expected_version=order.version,
        )
        self.assertEqual(order.status, OrderStatus.ACCEPTED)
        self.assertEqual(Product.objects.get(id=self.product.id).stock_quantity, initial_stock - 5)

    def test_customer_cancel_placed_order_keeps_stock_untouched(self):
        initial_stock = Product.objects.get(id=self.product.id).stock_quantity
        order = self._create_order(start_in_hours=30, cutoff_in_hours=18, qty=5)

        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.CANCELLED,
            actor=self.customer,
            actor_role=ActorRole.CUSTOMER,
            expected_version=order.version,
        )
        self.assertEqual(order.status, OrderStatus.CANCELLED)
        self.assertEqual(Product.objects.get(id=self.product.id).stock_quantity, initial_stock)

    def test_customer_cancel_accepted_order_restores_stock(self):
        initial_stock = Product.objects.get(id=self.product.id).stock_quantity
        order = self._create_order(start_in_hours=30, cutoff_in_hours=18, qty=5)

        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.ACCEPTED,
            actor=self.farmer_user,
            actor_role=ActorRole.FARMER,
            expected_version=order.version,
        )
        self.assertEqual(Product.objects.get(id=self.product.id).stock_quantity, initial_stock - 5)

        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.CANCELLED,
            actor=self.customer,
            actor_role=ActorRole.CUSTOMER,
            expected_version=order.version,
        )
        self.assertEqual(order.status, OrderStatus.CANCELLED)
        self.assertEqual(Product.objects.get(id=self.product.id).stock_quantity, initial_stock)

    def test_farmer_decline_placed_order_keeps_stock_untouched(self):
        initial_stock = Product.objects.get(id=self.product.id).stock_quantity
        order = self._create_order(start_in_hours=24, cutoff_in_hours=12, qty=3)

        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.DECLINED,
            actor=self.farmer_user,
            actor_role=ActorRole.FARMER,
            expected_version=order.version,
            reason="Out of cabbage today.",
        )
        self.assertEqual(order.status, OrderStatus.DECLINED)
        self.assertEqual(Product.objects.get(id=self.product.id).stock_quantity, initial_stock)

    def test_farmer_decline_accepted_order_restores_stock(self):
        initial_stock = Product.objects.get(id=self.product.id).stock_quantity
        order = self._create_order(start_in_hours=4, cutoff_in_hours=-2, qty=3)

        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.ACCEPTED,
            actor=self.farmer_user,
            actor_role=ActorRole.FARMER,
            expected_version=order.version,
        )
        self.assertEqual(Product.objects.get(id=self.product.id).stock_quantity, initial_stock - 3)

        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.DECLINED,
            actor=self.farmer_user,
            actor_role=ActorRole.FARMER,
            expected_version=order.version,
            reason="Heavy rain damaged harvest.",
            sold_out_product_ids=[],
        )
        self.assertEqual(order.status, OrderStatus.DECLINED)
        self.assertEqual(Product.objects.get(id=self.product.id).stock_quantity, initial_stock)

    def test_lazy_expiry_placed_order_keeps_stock_untouched(self):
        initial_stock = Product.objects.get(id=self.product.id).stock_quantity
        order = self._create_order(start_in_hours=-2, cutoff_in_hours=-14, qty=4)

        expired_count = expire_overdue_orders(farmer_id=self.farmer.pk)
        self.assertEqual(expired_count, 1)

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.EXPIRED)
        self.assertEqual(Product.objects.get(id=self.product.id).stock_quantity, initial_stock)

    def test_ready_for_pickup_before_cutoff_fails(self):
        order = self._create_order(start_in_hours=24, cutoff_in_hours=12, qty=2)
        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.ACCEPTED,
            actor=self.farmer_user,
            actor_role=ActorRole.FARMER,
            expected_version=order.version,
        )

        with self.assertRaises(UnprocessableEntityError) as ctx:
            transition_order(
                order_id=order.id,
                to_status=OrderStatus.READY_FOR_PICKUP,
                actor=self.farmer_user,
                actor_role=ActorRole.FARMER,
                expected_version=order.version,
            )
        self.assertEqual(ctx.exception.code, ErrorCode.CUTOFF_NOT_REACHED)

    def test_ready_for_pickup_blocked_by_pending_change(self):
        order = self._create_order(start_in_hours=2, cutoff_in_hours=-1, qty=2)
        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.ACCEPTED,
            actor=self.farmer_user,
            actor_role=ActorRole.FARMER,
            expected_version=order.version,
        )
        order.pending_change = {"items": [{"product_id": self.product.id, "quantity": 4}]}
        order.save()

        with self.assertRaises(UnprocessableEntityError) as ctx:
            transition_order(
                order_id=order.id,
                to_status=OrderStatus.READY_FOR_PICKUP,
                actor=self.farmer_user,
                actor_role=ActorRole.FARMER,
                expected_version=order.version,
            )
        self.assertEqual(ctx.exception.code, ErrorCode.FAILED_PRECONDITION)

    def test_no_show_before_pickup_end_fails(self):
        order = self._create_order(start_in_hours=2, cutoff_in_hours=-10, qty=2)
        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.ACCEPTED,
            actor=self.farmer_user,
            actor_role=ActorRole.FARMER,
            expected_version=order.version,
        )

        with self.assertRaises(UnprocessableEntityError) as ctx:
            transition_order(
                order_id=order.id,
                to_status=OrderStatus.NO_SHOW,
                actor=self.farmer_user,
                actor_role=ActorRole.FARMER,
                expected_version=order.version,
            )
        self.assertEqual(ctx.exception.code, ErrorCode.PICKUP_NOT_ENDED)

        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.READY_FOR_PICKUP,
            actor=self.farmer_user,
            actor_role=ActorRole.FARMER,
            expected_version=order.version,
        )

        with self.assertRaises(UnprocessableEntityError) as ctx:
            transition_order(
                order_id=order.id,
                to_status=OrderStatus.NO_SHOW,
                actor=self.farmer_user,
                actor_role=ActorRole.FARMER,
                expected_version=order.version,
            )
        self.assertEqual(ctx.exception.code, ErrorCode.PICKUP_NOT_ENDED)

    def test_no_show_from_ready_restores_stock(self):
        initial_stock = Product.objects.get(id=self.product.id).stock_quantity
        order = self._create_order(start_in_hours=2, cutoff_in_hours=-1, qty=3)

        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.ACCEPTED,
            actor=self.farmer_user,
            actor_role=ActorRole.FARMER,
            expected_version=order.version,
        )
        self.assertEqual(Product.objects.get(id=self.product.id).stock_quantity, initial_stock - 3)

        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.READY_FOR_PICKUP,
            actor=self.farmer_user,
            actor_role=ActorRole.FARMER,
            expected_version=order.version,
        )

        order.pickup_start_at = timezone.now() - timedelta(hours=3)
        order.cutoff_at = timezone.now() - timedelta(hours=15)
        order.pickup_end_at = timezone.now() - timedelta(hours=1)
        order.save(update_fields=["pickup_start_at", "cutoff_at", "pickup_end_at"])

        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.NO_SHOW,
            actor=self.farmer_user,
            actor_role=ActorRole.FARMER,
            expected_version=order.version,
        )
        self.assertEqual(order.status, OrderStatus.NO_SHOW)
        self.assertEqual(Product.objects.get(id=self.product.id).stock_quantity, initial_stock)

    def test_no_show_from_accepted_restores_stock(self):
        initial_stock = Product.objects.get(id=self.product.id).stock_quantity
        order = self._create_order(start_in_hours=24, cutoff_in_hours=12, qty=4)

        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.ACCEPTED,
            actor=self.farmer_user,
            actor_role=ActorRole.FARMER,
            expected_version=order.version,
        )
        self.assertEqual(Product.objects.get(id=self.product.id).stock_quantity, initial_stock - 4)

        order.pickup_start_at = timezone.now() - timedelta(hours=3)
        order.cutoff_at = timezone.now() - timedelta(hours=15)
        order.pickup_end_at = timezone.now() - timedelta(hours=1)
        order.save(update_fields=["pickup_start_at", "cutoff_at", "pickup_end_at"])

        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.NO_SHOW,
            actor=self.farmer_user,
            actor_role=ActorRole.FARMER,
            expected_version=order.version,
        )
        self.assertEqual(order.status, OrderStatus.NO_SHOW)
        self.assertEqual(Product.objects.get(id=self.product.id).stock_quantity, initial_stock)

    def test_actor_role_enforcement(self):
        order = self._create_order(start_in_hours=24, cutoff_in_hours=12, qty=2)

        with self.assertRaises(ForbiddenActionError):
            transition_order(
                order_id=order.id,
                to_status=OrderStatus.ACCEPTED,
                actor=self.customer,
                actor_role=ActorRole.CUSTOMER,
                expected_version=order.version,
            )

    def test_occ_conflict_on_stale_version(self):
        order = self._create_order(start_in_hours=24, cutoff_in_hours=12, qty=2)

        with self.assertRaises(ConflictError) as ctx:
            transition_order(
                order_id=order.id,
                to_status=OrderStatus.ACCEPTED,
                actor=self.farmer_user,
                actor_role=ActorRole.FARMER,
                expected_version=999,
            )
        self.assertEqual(ctx.exception.code, ErrorCode.RESOURCE_MODIFIED)

    def test_admin_suspend_farmer_uses_system_reason_constant(self):
        order = self._create_order(start_in_hours=24, cutoff_in_hours=12, qty=2)

        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.DECLINED,
            actor=self.admin_user,
            actor_role=ActorRole.ADMIN,
            expected_version=order.version,
            reason="Investigating fraud complaints",
        )
        self.assertEqual(order.status, OrderStatus.DECLINED)
        history = order.status_history.last()
        self.assertEqual(history.change_reason, ChangeReason.FARMER_SUSPENDED_BY_ADMIN)


    def _locked_notification(self, order: Order) -> Notification:
        return Notification.objects.get(
            recipient=self.farmer_user,
            type=NotificationType.ORDER_CANCELLED_CUSTOMER_LOCKED,
            target_url=f"/farmer/orders/{order.id}",
        )

    def test_admin_cancel_placed_order_says_stock_unchanged(self):
        order = self._create_order(start_in_hours=24, cutoff_in_hours=12, qty=2)
        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.CANCELLED,
            actor=self.admin_user,
            actor_role=ActorRole.ADMIN,
            expected_version=order.version,
        )
        self.assertEqual(order.status, OrderStatus.CANCELLED)
        self.assertEqual(Product.objects.get(id=self.product.id).stock_quantity, 50)

        message = self._locked_notification(order).message
        self.assertIn("stock did not change", message)
        self.assertNotIn("returned", message)

    def test_admin_cancel_accepted_order_says_stock_returned(self):
        order = self._create_order(start_in_hours=24, cutoff_in_hours=12, qty=2)
        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.ACCEPTED,
            actor=self.farmer_user,
            actor_role=ActorRole.FARMER,
            expected_version=order.version,
        )
        self.assertEqual(Product.objects.get(id=self.product.id).stock_quantity, 48)

        order = transition_order(
            order_id=order.id,
            to_status=OrderStatus.CANCELLED,
            actor=self.admin_user,
            actor_role=ActorRole.ADMIN,
            expected_version=order.version,
        )
        self.assertEqual(Product.objects.get(id=self.product.id).stock_quantity, 50)
        self.assertIn("returned to your online stock", self._locked_notification(order).message)
