from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CustomUser, CustomerProfile, FarmerProfile, FarmerStatus, Role, RoleCode
from catalog.models import Category, Product, Unit
from markets.models import FarmerClosure, FarmerMarket, Market, MarketOperatingDay, PickupSlot
from orders.models import Order, OrderItem, OrderStatus
from system.models import AuditAction, AuditLog
from system.selectors import build_change_log

_S = OrderStatus


@override_settings(GEOCODING_ENABLED=False)
class AuditTrailTestCase(TestCase):
    """v1.8 audit trail: every Farmer write leaves a history row (who, when, why, old -> new)."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        farmer_role, _ = Role.objects.get_or_create(code=RoleCode.FARMER, defaults={"name": "Farmer"})
        customer_role, _ = Role.objects.get_or_create(code=RoleCode.CUSTOMER, defaults={"name": "Customer"})
        self.farmer_user = CustomUser.objects.create(email="trail_farmer@marketlink.local", role=farmer_role)
        self.farmer = FarmerProfile.objects.create(
            user=self.farmer_user,
            stall_name="Trail Stall",
            contact_person="Trail Farmer",
            phone="0933100100",
            address="1 Trail Road",
            status=FarmerStatus.APPROVED,
            operating_days=[1, 2, 3, 4, 5, 6, 7],
        )
        self.customer = CustomUser.objects.create(email="trail_customer@marketlink.local", role=customer_role)
        CustomerProfile.objects.create(user=self.customer, full_name="Khach T", phone="0911600100", address="2 Road")
        self.market = Market.objects.create(
            name="Trail Market",
            address="Market address",
            latitude=Decimal("10.770000"),
            longitude=Decimal("106.700000"),
            open_time="05:00",
            close_time="20:00",
        )
        for day in range(1, 8):
            MarketOperatingDay.objects.create(market=self.market, day_of_week=day)
        self.farmer_market = FarmerMarket.objects.create(farmer=self.farmer, market=self.market, stall_label="T1")
        self.slot = PickupSlot.objects.create(
            farmer_market=self.farmer_market, day_of_week=1, start_time="07:00", end_time="09:00"
        )
        category = Category.objects.create(name="Greens")
        self.product = Product.objects.create(
            farmer=self.farmer, category=category, name="Spinach", unit=Unit.KG,
            price=Decimal("2.00"), stock_quantity=10, weekly_default_quantity=20,
        )
        self.product_b = Product.objects.create(
            farmer=self.farmer, category=category, name="Lettuce", unit=Unit.KG,
            price=Decimal("1.50"), stock_quantity=10,
        )
        self.client.force_authenticate(user=self.farmer_user)

    # --- helpers ---

    def _order(self, status=_S.PLACED, *, days_ahead=3, items=None) -> Order:
        pickup_date = timezone.localdate() + timedelta(days=days_ahead)
        start_at = timezone.make_aware(datetime.combine(pickup_date, time(7, 0)), timezone.get_current_timezone())
        items = items or [(self.product, 2, Decimal("2.00"))]
        order = Order.objects.create(
            customer=self.customer,
            farmer=self.farmer,
            market=self.market,
            pickup_slot=self.slot,
            stall_label="T1",
            pickup_date=pickup_date,
            pickup_start_at=start_at,
            pickup_end_at=start_at + timedelta(hours=2),
            cutoff_at=start_at - timedelta(hours=12),
            total_amount=sum((price * qty for _, qty, price in items), Decimal("0.00")),
            status=status,
        )
        for product, qty, price in items:
            OrderItem.objects.create(
                order=order, product=product, product_name=product.name, unit=product.unit,
                unit_price=price, quantity=qty, line_total=price * qty,
            )
        return order

    def _latest(self, model, object_id):
        return model.history.filter(**{model._meta.pk.attname: object_id}).order_by("-history_date", "-history_id").first()

    # --- products ---

    def test_price_change_is_traced_with_old_and_new_value(self):
        res = self.client.patch(f"/api/farmer/products/{self.product.pk}/", {"price": "3.50"}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        log = build_change_log(Product, self.product.pk)
        self.assertEqual([entry["type"] for entry in log], ["CREATED", "UPDATED"])
        self.assertEqual(log[-1]["user"], {"id": self.farmer_user.pk, "email": self.farmer_user.email})
        # build_change_log returns JSON-safe values (AD-34 serves them as-is): Decimal -> string.
        self.assertIn({"field": "price", "old": "2.00", "new": "3.50"}, log[-1]["changes"])

    def test_accepting_an_order_traces_stock_with_the_order(self):
        order = self._order()
        res = self.client.post(f"/api/farmer/orders/{order.pk}/accept/", {}, format="json", HTTP_IF_MATCH=str(order.version))
        self.assertEqual(res.status_code, 200, res.data)
        record = self._latest(Product, self.product.pk)
        self.assertEqual(record.stock_quantity, 8)
        self.assertEqual(record.history_user, self.farmer_user)
        self.assertIn(f"Order #{order.pk}", record.history_change_reason)
        self.assertIn("(T2)", record.history_change_reason)
        order_record = self._latest(Order, order.pk)
        self.assertEqual(order_record.status, _S.ACCEPTED)
        self.assertIn("(T2)", order_record.history_change_reason)

    def test_system_expiry_is_recorded_without_user(self):
        order = self._order(days_ahead=-1)
        self.assertEqual(self.client.get("/api/farmer/orders/", {"tab": "placed"}).status_code, 200)  # lazy sweep
        record = self._latest(Order, order.pk)
        self.assertEqual(record.status, _S.EXPIRED)
        self.assertIsNone(record.history_user)
        self.assertIn("(T8)", record.history_change_reason)

    def test_mark_sold_out_and_weekly_template(self):
        self.client.post(f"/api/farmer/products/{self.product.pk}/mark-sold-out/", {})
        self.assertEqual(self._latest(Product, self.product.pk).history_change_reason, "Marked sold out by farmer")
        res = self.client.post("/api/farmer/products/apply-weekly-template/", {})
        self.assertEqual(res.status_code, 200, res.data)
        record = self._latest(Product, self.product.pk)
        self.assertEqual(record.stock_quantity, 20)
        self.assertTrue(record.history_change_reason.startswith("Weekly template applied"))

    # --- orders ---

    def test_change_request_keeps_the_items_before_the_change(self):
        order = self._order(_S.ACCEPTED, items=[(self.product, 2, Decimal("2.00")), (self.product_b, 1, Decimal("1.50"))])
        old_items = {item.product_id: item.pk for item in order.items.all()}
        order.pending_change = {
            "items": [{"product_id": self.product.pk, "quantity": 3, "unit_price": "2.00"}],
            "pickup_date": None,
            "pickup_slot_id": None,
            "note": None,
            "requested_at": timezone.now().isoformat(),
        }
        order.save(update_fields=["pending_change"])
        res = self.client.post(
            f"/api/farmer/orders/{order.pk}/change-request/approve/", {}, format="json", HTTP_IF_MATCH=str(order.version)
        )
        self.assertEqual(res.status_code, 200, res.data)

        reason = f"Order #{order.pk}: change request approved"
        removed = OrderItem.history.filter(id=old_items[self.product_b.pk], history_type="-").get()
        self.assertEqual((removed.quantity, removed.unit_price, removed.history_change_reason), (1, Decimal("1.50"), reason))
        self.assertEqual(removed.history_user, self.farmer_user)
        new_item = order.items.get()
        self.assertTrue(OrderItem.history.filter(id=new_item.pk, history_type="+", history_change_reason=reason).exists())
        self.assertEqual(self._latest(Order, order.pk).history_change_reason, reason)
        # Stock delta of the change (+1 lettuce back, -1 spinach) is traced too.
        self.assertEqual(self._latest(Product, self.product_b.pk).history_change_reason, reason)

    def test_item_marked_sold_out_is_traced(self):
        order = self._order(items=[(self.product, 2, Decimal("2.00")), (self.product_b, 4, Decimal("1.50"))])
        item_b = order.items.get(product=self.product_b)
        res = self.client.post(
            f"/api/farmer/orders/{order.pk}/items/{self.product_b.pk}/mark-sold-out/", {}, format="json",
            HTTP_IF_MATCH=str(order.version),
        )
        self.assertEqual(res.status_code, 200, res.data)
        removed = OrderItem.history.filter(id=item_b.pk, history_type="-").get()
        self.assertEqual((removed.quantity, removed.unit_price), (4, Decimal("1.50")))
        self.assertIn("marked sold out (Lettuce)", removed.history_change_reason)
        self.assertEqual(self._latest(Product, self.product_b.pk).stock_quantity, 0)

    # --- markets, slots, time off ---

    def test_market_join_rename_and_leave(self):
        other_market = Market.objects.create(
            name="Second Market", address="x", latitude=Decimal("10"), longitude=Decimal("106"),
            open_time="05:00", close_time="20:00",
        )
        MarketOperatingDay.objects.create(market=other_market, day_of_week=2)
        fm_id = self.client.post("/api/farmer/markets/", {"market_id": other_market.pk, "stall_label": "A1"}, format="json").data["data"]["id"]
        self.client.patch(f"/api/farmer/markets/{fm_id}/", {"stall_label": "B2"}, format="json")
        slot_id = self.client.post(
            "/api/farmer/pickup-slots/",
            {"farmer_market_id": fm_id, "day_of_week": 2, "start_time": "07:00", "end_time": "08:00"},
            format="json",
        ).data["data"]["id"]
        self.assertEqual(self.client.delete(f"/api/farmer/markets/{fm_id}/").status_code, 204)

        log = build_change_log(FarmerMarket, fm_id)
        self.assertEqual([entry["type"] for entry in log], ["CREATED", "UPDATED", "DELETED"])
        self.assertIn({"field": "stall_label", "old": "A1", "new": "B2"}, log[1]["changes"])
        self.assertEqual(log[-1]["reason"], f"Farmer left market #{other_market.pk}")
        slot_log = build_change_log(PickupSlot, slot_id)
        self.assertEqual(slot_log[-1]["type"], "DELETED")
        self.assertEqual(slot_log[-1]["reason"], f"Farmer left market #{other_market.pk}")

    def test_slot_create_update_delete(self):
        slot_id = self.client.post(
            "/api/farmer/pickup-slots/",
            {"farmer_market_id": self.farmer_market.pk, "day_of_week": 3, "start_time": "07:00", "end_time": "09:00"},
            format="json",
        ).data["data"]["id"]
        self.client.patch(f"/api/farmer/pickup-slots/{slot_id}/", {"end_time": "10:00"}, format="json")
        self.client.delete(f"/api/farmer/pickup-slots/{slot_id}/")
        log = build_change_log(PickupSlot, slot_id)
        self.assertEqual([entry["type"] for entry in log], ["CREATED", "UPDATED", "DELETED"])
        self.assertEqual(log[1]["changes"], [{"field": "end_time", "old": "09:00:00", "new": "10:00:00"}])
        self.assertTrue(all(entry["user"]["id"] == self.farmer_user.pk for entry in log))

    def test_slots_switched_off_by_operating_day_change(self):
        res = self.client.patch("/api/farmer/profile/", {"operating_days": [2, 3, 4, 5, 6, 7]}, format="json")
        self.assertEqual(res.status_code, 200, res.data)
        record = self._latest(PickupSlot, self.slot.pk)
        self.assertFalse(record.is_active)
        self.assertEqual(record.history_change_reason, "Switched off: day 1 is no longer an operating day")
        profile_log = build_change_log(FarmerProfile, self.farmer.pk)
        self.assertIn(
            {"field": "operating_days", "old": [1, 2, 3, 4, 5, 6, 7], "new": [2, 3, 4, 5, 6, 7]},
            profile_log[-1]["changes"],
        )

    def test_time_off_create_and_delete(self):
        today = timezone.localdate()
        closure_id = self.client.post(
            "/api/farmer/closures/",
            {"start_date": (today + timedelta(days=10)).isoformat(), "end_date": (today + timedelta(days=11)).isoformat()},
            format="json",
        ).data["data"]["id"]
        self.client.delete(f"/api/farmer/closures/{closure_id}/")
        log = build_change_log(FarmerClosure, closure_id)
        self.assertEqual([entry["type"] for entry in log], ["CREATED", "DELETED"])
        self.assertEqual(log[-1]["user"]["id"], self.farmer_user.pk)

    # --- registration (audit_logs) ---

    def test_registration_is_logged_without_ip(self):
        client = APIClient()
        with mock.patch("accounts.services.registration.geocode_address", return_value=None):
            res = client.post(
                "/api/auth/register/farmer/",
                {
                    "email": "new_trail@example.com", "password": "garden2026", "confirm_password": "garden2026",
                    "stall_name": "New Trail", "contact_person": "Nguyen Moi", "phone": "0912700700",
                    "address": "9 Le Loi, District 1", "operating_days": [1, 3],
                },
                format="json",
                REMOTE_ADDR="203.0.113.9",
            )
        self.assertEqual(res.status_code, 201, res.data)
        user = CustomUser.objects.get(email="new_trail@example.com")
        entry = AuditLog.objects.get(action=AuditAction.ACCOUNT_REGISTERED, user=user)
        self.assertIsNone(entry.ip_address)
        self.assertIsNone(entry.user_agent)
        self.assertEqual(entry.status_code, 201)
        self.assertEqual(entry.details, {"role": RoleCode.FARMER})
        self.assertEqual(build_change_log(FarmerProfile, user.pk)[0]["type"], "CREATED")
