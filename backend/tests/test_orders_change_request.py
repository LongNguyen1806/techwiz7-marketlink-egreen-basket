from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounts.models import (
    CustomUser,
    CustomerProfile,
    FarmerProfile,
    FarmerStatus,
    Role,
    RoleCode,
)
from catalog.models import Category, Product, ReviewStatus, Unit
from marketlink_core.exceptions import (
    BusinessValidationError,
    ConflictError,
    ErrorCode,
    ForbiddenActionError,
    PreconditionRequiredError,
    ResourceNotFoundError,
    UnprocessableEntityError,
)
from markets.models import FarmerMarket, Market, MarketOperatingDay, PickupSlot
from notifications.models import Notification, NotificationType
from orders.models import ActorRole, Order, OrderItem, OrderStatus
from orders.services.farmer_change_request import approve_change_request, reject_change_request
from orders.services.fsm import record_order_placed, transition_order


class FarmerChangeRequestTestCase(TestCase):
    def setUp(self):
        customer_role, _ = Role.objects.get_or_create(
            code=RoleCode.CUSTOMER, defaults={"name": "Customer"}
        )
        farmer_role, _ = Role.objects.get_or_create(
            code=RoleCode.FARMER, defaults={"name": "Farmer"}
        )

        self.customer = CustomUser.objects.create(
            email="cust_cr@marketlink.local",
            role=customer_role,
        )
        CustomerProfile.objects.create(
            user=self.customer,
            full_name="Hoang Customer",
            phone="0911777888",
            address="123 Customer Ave",
        )

        self.farmer_user = CustomUser.objects.create(
            email="farmer_cr@marketlink.local",
            role=farmer_role,
        )
        self.farmer = FarmerProfile.objects.create(
            operating_days=[1, 2, 3, 4, 5, 6, 7],
            user=self.farmer_user,
            stall_name="Sunshine Organic",
            contact_person="Nguyen Farmer",
            phone="0988111222",
            address="456 Farm Valley",
            order_cutoff_hours=12,
        )

        self.other_farmer_user = CustomUser.objects.create(
            email="other_farmer_cr@marketlink.local",
            role=farmer_role,
        )
        self.other_farmer = FarmerProfile.objects.create(
            operating_days=[1, 2, 3, 4, 5, 6, 7],
            user=self.other_farmer_user,
            stall_name="Moonlight Farm",
            contact_person="Pham Farmer",
            phone="0988333444",
            address="789 Farm Hill",
            order_cutoff_hours=12,
        )

        self.market = Market.objects.create(
            name="City Fresh Market",
            address="500 Market Square",
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

        self.category = Category.objects.create(name="Produce")
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

    def _create_accepted_order_with_change_request(
        self,
        new_items: list[dict] | None = None,
        is_overdue: bool = False,
    ) -> Order:
        now = timezone.now()
        if is_overdue:
            start_at = now - timedelta(hours=2)
            end_at = now - timedelta(hours=1)
            cutoff_at = now - timedelta(hours=14)
        else:
            start_at = now + timedelta(hours=48)
            end_at = start_at + timedelta(hours=2)
            cutoff_at = now + timedelta(hours=36)

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
            total_amount=Decimal("25.00"),
            status=OrderStatus.PLACED,
        )
        OrderItem.objects.create(
            order=order,
            product=self.product1,
            product_name=self.product1.name,
            unit=self.product1.unit,
            unit_price=self.product1.price,
            quantity=2,
            line_total=Decimal("20.00"),
        )
        OrderItem.objects.create(
            order=order,
            product=self.product2,
            product_name=self.product2.name,
            unit=self.product2.unit,
            unit_price=self.product2.price,
            quantity=1,
            line_total=Decimal("5.00"),
        )
        record_order_placed(order=order, actor=self.customer)

        if not is_overdue:
            order = transition_order(
                order_id=order.id,
                to_status=OrderStatus.ACCEPTED,
                actor=self.farmer_user,
                actor_role=ActorRole.FARMER,
                expected_version=order.version,
            )
        else:
            order.status = OrderStatus.ACCEPTED
            self.product1.stock_quantity -= 2
            self.product1.save(update_fields=["stock_quantity"])
            self.product2.stock_quantity -= 1
            self.product2.save(update_fields=["stock_quantity"])
            order.save(update_fields=["status"])

        if new_items is None:
            new_items = [
                {
                    "product_id": self.product1.id,
                    "product_name": self.product1.name,
                    "quantity": 3,
                    "unit": self.product1.unit,
                    "unit_price": "10.00",
                },
            ]

        order.pending_change = {
            "items": new_items,
            "pickup_date": None,
            "pickup_slot_id": None,
            "note": "Updated note from customer",
            "change_summary": "Changed spinach from 2 to 3, removed mint",
            "requested_at": now.isoformat(),
        }
        order.version += 1
        order.save(update_fields=["pending_change", "version"])
        return order

    def test_approve_change_request_reconciles_stock_deltas(self):
        order = self._create_accepted_order_with_change_request()
        self.product1.refresh_from_db()
        self.product2.refresh_from_db()
        self.assertEqual(self.product1.stock_quantity, 48)
        self.assertEqual(self.product2.stock_quantity, 29)

        initial_version = order.version
        updated_order = approve_change_request(
            order_id=order.id,
            farmer_id=self.farmer.pk,
            expected_version=initial_version,
            actor=self.farmer_user,
        )

        self.assertIsNone(updated_order.pending_change)
        self.assertEqual(updated_order.version, initial_version + 1)
        self.assertEqual(updated_order.status, OrderStatus.ACCEPTED)
        self.assertEqual(updated_order.total_amount, Decimal("30.00"))
        self.assertEqual(updated_order.note, "Updated note from customer")

        self.product1.refresh_from_db()
        self.product2.refresh_from_db()
        self.assertEqual(self.product1.stock_quantity, 47)
        self.assertEqual(self.product2.stock_quantity, 30)

        items = list(updated_order.items.all())
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].product_id, self.product1.id)
        self.assertEqual(items[0].quantity, 3)
        self.assertEqual(items[0].line_total, Decimal("30.00"))

        history = updated_order.status_history.order_by("-id").first()
        self.assertIsNotNone(history)
        self.assertIsNone(history.transition)
        self.assertEqual(history.from_status, OrderStatus.ACCEPTED)
        self.assertEqual(history.to_status, OrderStatus.ACCEPTED)
        self.assertEqual(history.actor_role, ActorRole.FARMER)
        self.assertEqual(history.change_reason, "Farmer approved change request")

        notif = Notification.objects.filter(
            recipient=self.customer, type=NotificationType.ORDER_CHANGE_APPROVED
        ).first()
        self.assertIsNotNone(notif)
        self.assertIn("approved", notif.title.lower())

    def test_approve_change_request_insufficient_stock(self):
        order = self._create_accepted_order_with_change_request(
            new_items=[
                {
                    "product_id": self.product1.id,
                    "product_name": self.product1.name,
                    "quantity": 100,
                    "unit": self.product1.unit,
                    "unit_price": "10.00",
                }
            ]
        )

        with self.assertRaises(BusinessValidationError) as ctx:
            approve_change_request(
                order_id=order.id,
                farmer_id=self.farmer.pk,
                expected_version=order.version,
                actor=self.farmer_user,
            )
        self.assertEqual(ctx.exception.code, ErrorCode.INSUFFICIENT_STOCK)

        order.refresh_from_db()
        self.assertIsNotNone(order.pending_change)
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock_quantity, 48)

    def test_reject_change_request_preserves_original_order(self):
        order = self._create_accepted_order_with_change_request()
        initial_version = order.version

        updated_order = reject_change_request(
            order_id=order.id,
            farmer_id=self.farmer.pk,
            expected_version=initial_version,
            actor=self.farmer_user,
            reason="Sorry, we cannot accommodate this change.",
        )

        self.assertIsNone(updated_order.pending_change)
        self.assertEqual(updated_order.version, initial_version + 1)
        self.assertEqual(updated_order.status, OrderStatus.ACCEPTED)
        self.assertEqual(updated_order.total_amount, Decimal("25.00"))

        self.product1.refresh_from_db()
        self.product2.refresh_from_db()
        self.assertEqual(self.product1.stock_quantity, 48)
        self.assertEqual(self.product2.stock_quantity, 29)

        self.assertEqual(updated_order.items.count(), 2)

        history = updated_order.status_history.order_by("-id").first()
        self.assertIsNotNone(history)
        self.assertIsNone(history.transition)
        self.assertIn("Sorry, we cannot accommodate this change.", history.change_reason)

        notif = Notification.objects.filter(
            recipient=self.customer, type=NotificationType.ORDER_CHANGE_REJECTED
        ).first()
        self.assertIsNotNone(notif)
        self.assertIn("rejected", notif.title.lower())
        self.assertIn("Sorry, we cannot accommodate this change.", notif.message)

    def test_occ_conflict_on_approve_and_reject(self):
        order = self._create_accepted_order_with_change_request()

        with self.assertRaises(PreconditionRequiredError):
            approve_change_request(
                order_id=order.id,
                farmer_id=self.farmer.pk,
                expected_version=None,
                actor=self.farmer_user,
            )

        with self.assertRaises(ConflictError):
            approve_change_request(
                order_id=order.id,
                farmer_id=self.farmer.pk,
                expected_version=order.version + 99,
                actor=self.farmer_user,
            )

        with self.assertRaises(ConflictError):
            reject_change_request(
                order_id=order.id,
                farmer_id=self.farmer.pk,
                expected_version=order.version + 99,
                actor=self.farmer_user,
            )

    def test_cannot_act_after_pickup_started(self):
        order = self._create_accepted_order_with_change_request(is_overdue=True)

        with self.assertRaises(UnprocessableEntityError) as ctx:
            approve_change_request(
                order_id=order.id,
                farmer_id=self.farmer.pk,
                expected_version=order.version,
                actor=self.farmer_user,
            )
        self.assertEqual(ctx.exception.code, ErrorCode.PICKUP_ALREADY_STARTED)

        with self.assertRaises(UnprocessableEntityError) as ctx:
            reject_change_request(
                order_id=order.id,
                farmer_id=self.farmer.pk,
                expected_version=order.version,
                actor=self.farmer_user,
            )
        self.assertEqual(ctx.exception.code, ErrorCode.PICKUP_ALREADY_STARTED)

    def test_forbidden_for_other_or_suspended_farmer(self):
        order = self._create_accepted_order_with_change_request()

        with self.assertRaises(ResourceNotFoundError):
            approve_change_request(
                order_id=order.id,
                farmer_id=self.other_farmer.pk,
                expected_version=order.version,
                actor=self.other_farmer_user,
            )

        self.farmer.status = FarmerStatus.SUSPENDED
        self.farmer.save(update_fields=["status"])

        with self.assertRaises(ForbiddenActionError) as ctx:
            approve_change_request(
                order_id=order.id,
                farmer_id=self.farmer.pk,
                expected_version=order.version,
                actor=self.farmer_user,
            )
        self.assertEqual(ctx.exception.code, ErrorCode.FARMER_SUSPENDED)

    def test_cannot_act_without_pending_change(self):
        order = self._create_accepted_order_with_change_request()
        order.pending_change = None
        order.save(update_fields=["pending_change"])

        with self.assertRaises(UnprocessableEntityError) as ctx:
            approve_change_request(
                order_id=order.id,
                farmer_id=self.farmer.pk,
                expected_version=order.version,
                actor=self.farmer_user,
            )
        self.assertEqual(ctx.exception.code, ErrorCode.FAILED_PRECONDITION)


    def test_not_found_for_missing_or_foreign_order(self):
        order = self._create_accepted_order_with_change_request()
        with self.assertRaises(ResourceNotFoundError):
            reject_change_request(
                order_id=order.id,
                farmer_id=self.other_farmer.pk,
                expected_version=order.version + 99,
                actor=self.other_farmer_user,
            )
        with self.assertRaises(ResourceNotFoundError):
            approve_change_request(
                order_id=999999,
                farmer_id=self.farmer.pk,
                expected_version=1,
                actor=self.farmer_user,
            )

    def test_approve_change_request_with_reschedule(self):
        for day in range(1, 8):
            MarketOperatingDay.objects.create(market=self.market, day_of_week=day)
        new_date = (timezone.localtime(timezone.now()) + timedelta(days=3)).date()
        new_slot = PickupSlot.objects.create(
            farmer_market=self.farmer_market,
            day_of_week=new_date.isoweekday(),
            start_time="09:00:00",
            end_time="11:00:00",
            is_active=True,
        )
        order = self._create_accepted_order_with_change_request()
        order.pending_change = {
            "items": None,
            "pickup_date": new_date.isoformat(),
            "pickup_slot_id": new_slot.id,
            "note": None,
            "requested_at": timezone.now().isoformat(),
        }
        order.save(update_fields=["pending_change"])

        updated = approve_change_request(
            order_id=order.id,
            farmer_id=self.farmer.pk,
            expected_version=order.version,
            actor=self.farmer_user,
        )
        updated.refresh_from_db()
        self.assertIsNone(updated.pending_change)
        self.assertEqual(updated.pickup_date, new_date)
        self.assertEqual(updated.pickup_slot_id, new_slot.id)
        self.assertEqual(timezone.localtime(updated.pickup_start_at).hour, 9)
        self.assertEqual(timezone.localtime(updated.pickup_end_at).hour, 11)
        self.assertEqual(updated.cutoff_at, updated.pickup_start_at - timedelta(hours=12))
        self.assertEqual(updated.stall_label, "Stall S1")
        self.assertEqual(updated.items.count(), 2)

    def test_malformed_pending_change_returns_422_not_500(self):
        order = self._create_accepted_order_with_change_request(
            new_items=[{"product_id": self.product1.id, "quantity": 3}]
        )
        with self.assertRaises(UnprocessableEntityError) as ctx:
            approve_change_request(
                order_id=order.id,
                farmer_id=self.farmer.pk,
                expected_version=order.version,
                actor=self.farmer_user,
            )
        self.assertEqual(ctx.exception.code, ErrorCode.FAILED_PRECONDITION)
        order.refresh_from_db()
        self.assertIsNotNone(order.pending_change)
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock_quantity, 48)

    def test_new_item_keeps_price_seen_by_customer(self):
        order = self._create_accepted_order_with_change_request(
            new_items=[
                {"product_id": self.product1.id, "quantity": 2, "unit_price": "10.00"},
                {"product_id": self.product2.id, "quantity": 2, "unit_price": "5.00"},
            ]
        )
        self.product2.price = Decimal("9.00")
        self.product2.save(update_fields=["price"])

        updated = approve_change_request(
            order_id=order.id,
            farmer_id=self.farmer.pk,
            expected_version=order.version,
            actor=self.farmer_user,
        )
        mint = updated.items.get(product=self.product2)
        self.assertEqual(mint.unit_price, Decimal("5.00"))
        self.assertEqual(updated.total_amount, Decimal("30.00"))
