from datetime import timedelta
from decimal import Decimal

from unittest import mock

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser, CustomerProfile, FarmerProfile, Role, RoleCode
from catalog.models import Category, Product, Unit
from catalog.services.farmer_product import apply_weekly_template
from catalog.services.stock import (
    get_held_quantities,
    get_pending_quantities,
    get_weekly_pattern_held_quantities,
)
from markets.models import FarmerMarket, Market, PickupSlot
from notifications.models import Notification, NotificationType
from orders.models import ActorRole, Order, OrderItem, OrderStatus, Transition
from orders.services import expiry as expiry_service
from orders.services.expiry import expire_overdue_orders
from orders.services.fsm import record_order_placed, transition_order


class OrderExpiryTestCase(TestCase):
    def setUp(self):
        customer_role, _ = Role.objects.get_or_create(
            code=RoleCode.CUSTOMER, defaults={"name": "Customer"}
        )
        farmer_role, _ = Role.objects.get_or_create(
            code=RoleCode.FARMER, defaults={"name": "Farmer"}
        )

        self.customer = CustomUser.objects.create(
            email="cust_expiry@marketlink.local",
            role=customer_role,
        )
        CustomerProfile.objects.create(
            user=self.customer,
            full_name="Le Van Test",
            phone="0911222333",
            address="123 Market Road",
        )

        self.farmer_user = CustomUser.objects.create(
            email="farmer_expiry@marketlink.local",
            role=farmer_role,
        )
        self.farmer = FarmerProfile.objects.create(
            operating_days=[1, 2, 3, 4, 5, 6, 7],
            user=self.farmer_user,
            stall_name="Green Orchard",
            contact_person="Tran Farmer",
            phone="0988777666",
            address="456 Farm Valley",
            order_cutoff_hours=6,
        )

        self.farmer_user2 = CustomUser.objects.create(
            email="farmer2_expiry@marketlink.local",
            role=farmer_role,
        )
        self.farmer2 = FarmerProfile.objects.create(
            operating_days=[1, 2, 3, 4, 5, 6, 7],
            user=self.farmer_user2,
            stall_name="Berry Fields",
            contact_person="Vo Farmer",
            phone="0988777111",
            address="789 Farm Hill",
            order_cutoff_hours=6,
        )

        self.market = Market.objects.create(
            name="Community Market",
            address="100 Market Way",
            latitude=Decimal("10.7769"),
            longitude=Decimal("106.7009"),
            open_time="06:00:00",
            close_time="20:00:00",
        )
        self.farmer_market = FarmerMarket.objects.create(
            farmer=self.farmer,
            market=self.market,
            stall_label="Stall E1",
        )
        self.farmer_market2 = FarmerMarket.objects.create(
            farmer=self.farmer2,
            market=self.market,
            stall_label="Stall E2",
        )

        self.category = Category.objects.create(name="Vegetables")
        self.product = Product.objects.create(
            farmer=self.farmer,
            category=self.category,
            name="Organic Carrots",
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

    def _create_order(
        self,
        farmer: FarmerProfile,
        is_overdue: bool = False,
        status: str = OrderStatus.PLACED,
        qty: int = 2,
    ) -> Order:
        now = timezone.now()
        if is_overdue:
            start_at = now - timedelta(hours=2)
            end_at = now - timedelta(hours=1)
            cutoff_at = now - timedelta(hours=8)
        else:
            start_at = now + timedelta(hours=24)
            end_at = start_at + timedelta(hours=2)
            cutoff_at = now + timedelta(hours=18)

        order = Order.objects.create(
            customer=self.customer,
            farmer=farmer,
            market=self.market,
            pickup_slot=self.slot,
            stall_label=f"Stall for {farmer.stall_name}",
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
        record_order_placed(order=order, actor=self.customer)
        return order

    def test_expire_overdue_placed_order(self):
        order = self._create_order(farmer=self.farmer, is_overdue=True)
        initial_stock = self.product.stock_quantity

        count = expire_overdue_orders(farmer_id=self.farmer.pk)
        self.assertEqual(count, 1)

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.EXPIRED)

        self.product.refresh_from_db()
        self.assertEqual(self.product.stock_quantity, initial_stock)

        history = order.status_history.order_by("-id").first()
        self.assertIsNotNone(history)
        self.assertEqual(history.transition, Transition.T8)
        self.assertEqual(history.actor_role, ActorRole.SYSTEM)
        self.assertEqual(history.change_reason, "SYSTEM_EXPIRED")

        notif = Notification.objects.filter(
            recipient=self.customer, type=NotificationType.ORDER_EXPIRED
        ).first()
        self.assertIsNotNone(notif)
        self.assertIn("expired", notif.title.lower())

    def test_active_placed_order_not_expired(self):
        order = self._create_order(farmer=self.farmer, is_overdue=False)

        count = expire_overdue_orders(farmer_id=self.farmer.pk)
        self.assertEqual(count, 0)

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.PLACED)

    def test_expire_overdue_pending_change(self):
        order = self._create_order(farmer=self.farmer, is_overdue=True, status=OrderStatus.ACCEPTED)
        order.pending_change = {
            "change_summary": "Added 1 Organic Carrots",
            "requested_at": timezone.now().isoformat(),
        }
        order.save(update_fields=["pending_change", "updated_at"])
        initial_version = order.version

        count = expire_overdue_orders(farmer_id=self.farmer.pk)
        self.assertEqual(count, 0)

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.ACCEPTED)
        self.assertIsNone(order.pending_change)
        self.assertEqual(order.version, initial_version + 1)

        history = order.status_history.order_by("-id").first()
        self.assertIsNotNone(history)
        self.assertIsNone(history.transition)
        self.assertEqual(history.actor_role, ActorRole.SYSTEM)
        self.assertEqual(history.change_reason, "Change request expired")

        notif = Notification.objects.filter(
            recipient=self.customer, type=NotificationType.ORDER_CHANGE_REJECTED
        ).first()
        self.assertIsNotNone(notif)
        self.assertIn("rejected", notif.title.lower())
        self.assertIn("did not respond before the pickup time", notif.message)

    def test_active_pending_change_not_expired(self):
        order = self._create_order(farmer=self.farmer, is_overdue=False, status=OrderStatus.ACCEPTED)
        order.pending_change = {
            "change_summary": "Added 1 Organic Carrots",
            "requested_at": timezone.now().isoformat(),
        }
        order.save(update_fields=["pending_change", "updated_at"])

        expire_overdue_orders(farmer_id=self.farmer.pk)

        order.refresh_from_db()
        self.assertIsNotNone(order.pending_change)

    def test_farmer_isolation_in_expiry(self):
        order_f1 = self._create_order(farmer=self.farmer, is_overdue=True)
        order_f2 = self._create_order(farmer=self.farmer2, is_overdue=True)

        count = expire_overdue_orders(farmer_id=self.farmer.pk)
        self.assertEqual(count, 1)

        order_f1.refresh_from_db()
        order_f2.refresh_from_db()
        self.assertEqual(order_f1.status, OrderStatus.EXPIRED)
        self.assertEqual(order_f2.status, OrderStatus.PLACED)

    def test_get_weekly_pattern_held_and_pending_quantities(self):
        self._create_order(farmer=self.farmer, is_overdue=False, status=OrderStatus.PLACED, qty=3)
        self._create_order(farmer=self.farmer, is_overdue=False, status=OrderStatus.ACCEPTED, qty=4)
        self._create_order(
            farmer=self.farmer, is_overdue=False, status=OrderStatus.READY_FOR_PICKUP, qty=2
        )
        self._create_order(farmer=self.farmer, is_overdue=True, status=OrderStatus.ACCEPTED, qty=5)

        held = get_weekly_pattern_held_quantities(product_ids=[self.product.id])
        self.assertEqual(held.get(self.product.id), 6)

        pending = get_pending_quantities(product_ids=[self.product.id])
        self.assertEqual(pending.get(self.product.id), 3)

        checkout_held = get_held_quantities(product_ids=[self.product.id])
        self.assertEqual(checkout_held.get(self.product.id), 3)

    def test_management_command_expire_orders(self):
        self._create_order(farmer=self.farmer, is_overdue=True)
        call_command("expire_orders", farmer_id=self.farmer.pk)

        overdue_remaining = Order.objects.filter(
            farmer=self.farmer, status=OrderStatus.PLACED, pickup_start_at__lte=timezone.now()
        ).count()
        self.assertEqual(overdue_remaining, 0)


    def test_apply_weekly_template_runs_lazy_sweep_first(self):
        order = self._create_order(farmer=self.farmer, is_overdue=True)
        apply_weekly_template(farmer=self.farmer)
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.EXPIRED)

    def test_one_failing_order_does_not_stop_the_sweep(self):
        broken = self._create_order(farmer=self.farmer, is_overdue=True)
        healthy = self._create_order(farmer=self.farmer, is_overdue=True)
        real_transition = expiry_service.transition_order

        def flaky_transition(*, order_id, **kwargs):
            if order_id == broken.id:
                raise RuntimeError("simulated failure")
            return real_transition(order_id=order_id, **kwargs)

        with mock.patch.object(expiry_service, "_in_caller_transaction", return_value=False), \
                mock.patch.object(expiry_service, "transition_order", side_effect=flaky_transition), \
                self.assertLogs("marketlink", level="ERROR"):
            count = expire_overdue_orders(farmer_id=self.farmer.pk)

        self.assertEqual(count, 1)
        broken.refresh_from_db()
        healthy.refresh_from_db()
        self.assertEqual(broken.status, OrderStatus.PLACED)
        self.assertEqual(healthy.status, OrderStatus.EXPIRED)

    def test_failure_inside_caller_transaction_is_raised(self):
        self._create_order(farmer=self.farmer, is_overdue=True)
        with mock.patch.object(
            expiry_service, "transition_order", side_effect=RuntimeError("simulated failure")
        ):
            with self.assertRaises(RuntimeError):
                expire_overdue_orders(farmer_id=self.farmer.pk)


    def test_weekly_held_counts_orders_inside_pickup_window(self):
        order = self._create_order(farmer=self.farmer, status=OrderStatus.ACCEPTED, qty=4)
        now = timezone.now()
        order.cutoff_at = now - timedelta(hours=3)
        order.pickup_start_at = now - timedelta(minutes=30)
        order.pickup_end_at = now + timedelta(minutes=90)
        order.save(update_fields=["cutoff_at", "pickup_start_at", "pickup_end_at"])

        held = get_weekly_pattern_held_quantities(product_ids=[self.product.id])
        self.assertEqual(held.get(self.product.id), 4)
