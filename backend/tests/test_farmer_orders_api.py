from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import (
    CustomUser,
    CustomerProfile,
    FarmerProfile,
    Role,
    RoleCode,
)
from catalog.models import Category, Product, ReviewStatus, Unit
from marketlink_core.exceptions import ErrorCode
from markets.models import FarmerMarket, Market, PickupSlot
from notifications.models import Notification, NotificationType
from orders.models import ActorRole, Order, OrderItem, OrderStatus, OrderStatusHistory
from orders.services.fsm import record_order_placed, transition_order


class FarmerOrdersAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        customer_role, _ = Role.objects.get_or_create(
            code=RoleCode.CUSTOMER, defaults={"name": "Customer"}
        )
        farmer_role, _ = Role.objects.get_or_create(
            code=RoleCode.FARMER, defaults={"name": "Farmer"}
        )

        self.customer = CustomUser.objects.create(
            email="cust_api@marketlink.local",
            role=customer_role,
        )
        CustomerProfile.objects.create(
            user=self.customer,
            full_name="Bui Customer",
            phone="0911555666",
            address="456 City Street",
        )

        self.farmer_user = CustomUser.objects.create(
            email="farmer_api@marketlink.local",
            role=farmer_role,
        )
        self.farmer = FarmerProfile.objects.create(
            operating_days=[1, 2, 3, 4, 5, 6, 7],
            user=self.farmer_user,
            stall_name="Highland Greenery",
            contact_person="Dang Farmer",
            phone="0988222333",
            address="100 Highland Way",
            order_cutoff_hours=6,
        )

        self.other_farmer_user = CustomUser.objects.create(
            email="other_farmer_api@marketlink.local",
            role=farmer_role,
        )
        self.other_farmer = FarmerProfile.objects.create(
            operating_days=[1, 2, 3, 4, 5, 6, 7],
            user=self.other_farmer_user,
            stall_name="Lowland Fields",
            contact_person="Do Farmer",
            phone="0988444555",
            address="200 Lowland Road",
            order_cutoff_hours=6,
        )

        self.market = Market.objects.create(
            name="Weekend Eco Market",
            address="88 Eco Street",
            latitude=Decimal("10.7769"),
            longitude=Decimal("106.7009"),
            open_time="06:00:00",
            close_time="20:00:00",
        )
        self.farmer_market = FarmerMarket.objects.create(
            farmer=self.farmer,
            market=self.market,
            stall_label="Stall H1",
        )

        self.category = Category.objects.create(name="Herbs")
        self.product1 = Product.objects.create(
            review_status=ReviewStatus.APPROVED,
            farmer=self.farmer,
            category=self.category,
            name="Coriander",
            unit=Unit.BUNCH,
            price=Decimal("4.00"),
            stock_quantity=40,
        )
        self.product2 = Product.objects.create(
            review_status=ReviewStatus.APPROVED,
            farmer=self.farmer,
            category=self.category,
            name="Basil",
            unit=Unit.BUNCH,
            price=Decimal("6.00"),
            stock_quantity=20,
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
        self,
        farmer: FarmerProfile,
        status: str = OrderStatus.PLACED,
        qty1: int = 2,
        qty2: int = 1,
        is_overdue: bool = False,
        pending_change: dict | None = None,
    ) -> Order:
        now = timezone.now()
        if is_overdue:
            start_at = now - timedelta(hours=2)
            end_at = now - timedelta(hours=1)
            cutoff_at = now - timedelta(hours=8)
        else:
            start_at = now + timedelta(hours=48)
            end_at = start_at + timedelta(hours=2)
            cutoff_at = now + timedelta(hours=42)

        total = self.product1.price * qty1 + self.product2.price * qty2
        order = Order.objects.create(
            customer=self.customer,
            farmer=farmer,
            market=self.market,
            pickup_slot=self.slot,
            stall_label="Stall H1",
            pickup_date=start_at.date(),
            pickup_start_at=start_at,
            pickup_end_at=end_at,
            cutoff_at=cutoff_at,
            total_amount=total,
            status=status,
            pending_change=pending_change,
        )
        if qty1 > 0:
            OrderItem.objects.create(
                order=order,
                product=self.product1,
                product_name=self.product1.name,
                unit=self.product1.unit,
                unit_price=self.product1.price,
                quantity=qty1,
                line_total=self.product1.price * qty1,
            )
        if qty2 > 0:
            OrderItem.objects.create(
                order=order,
                product=self.product2,
                product_name=self.product2.name,
                unit=self.product2.unit,
                unit_price=self.product2.price,
                quantity=qty2,
                line_total=self.product2.price * qty2,
            )
        record_order_placed(order=order, actor=self.customer)
        return order

    def test_permission_denied_for_unauthenticated_or_customer(self):
        res = self.client.get("/api/farmer/orders/")
        self.assertEqual(res.status_code, 401)

        self.client.force_authenticate(user=self.customer)
        res = self.client.get("/api/farmer/orders/")
        self.assertEqual(res.status_code, 403)

    def test_get_farmer_orders_list_tabs_and_counts(self):
        placed = self._create_order(farmer=self.farmer, status=OrderStatus.PLACED)
        self._create_order(farmer=self.farmer, status=OrderStatus.ACCEPTED)
        self._create_order(
            farmer=self.farmer,
            status=OrderStatus.ACCEPTED,
            pending_change={"items": [], "change_summary": "Test change"},
        )
        self._create_order(farmer=self.farmer, status=OrderStatus.READY_FOR_PICKUP)
        self._create_order(farmer=self.farmer, status=OrderStatus.COMPLETED)

        self.client.force_authenticate(user=self.farmer_user)

        res = self.client.get("/api/farmer/orders/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(len(res.data["data"]["results"]), 1)
        self.assertNotIn("tab_counts", res.data["data"])

        for tab, expected in (("placed", 1), ("accepted", 2), ("ready", 1), ("history", 1)):
            res_tab = self.client.get(f"/api/farmer/orders/?tab={tab}")
            self.assertEqual(res_tab.status_code, 200, tab)
            self.assertEqual(len(res_tab.data["data"]["results"]), expected, tab)

        res_cr = self.client.get("/api/farmer/orders/?tab=accepted&change_requested=true")
        self.assertEqual(len(res_cr.data["data"]["results"]), 1)

        counts = self.client.get("/api/farmer/orders/tab-counts/").data["data"]
        self.assertEqual(
            counts,
            {
                "placed": 1,
                "accepted": 2,
                "ready": 1,
                "overdue": 0,
                "change_requests": 1,
                "by_date": {placed.pickup_date.isoformat(): {"placed": 1, "accepted": 2, "ready": 1}},
            },
        )

    def test_get_order_detail_and_allowed_actions(self):
        order = self._create_order(farmer=self.farmer, status=OrderStatus.PLACED)
        self.client.force_authenticate(user=self.farmer_user)

        res = self.client.get(f"/api/farmer/orders/{order.id}/")
        self.assertEqual(res.status_code, 200)
        detail = res.data["data"]
        self.assertEqual(detail["id"], order.id)
        self.assertIn("ACCEPT", detail["allowed_actions"])
        self.assertIn("DECLINE", detail["allowed_actions"])

        other_order = self._create_order(farmer=self.other_farmer, status=OrderStatus.PLACED)
        res_other = self.client.get(f"/api/farmer/orders/{other_order.id}/")
        self.assertEqual(res_other.status_code, 404)

    def test_accept_order_api(self):
        order = self._create_order(farmer=self.farmer, status=OrderStatus.PLACED, qty1=2, qty2=1)
        self.client.force_authenticate(user=self.farmer_user)

        res_missing = self.client.post(f"/api/farmer/orders/{order.id}/accept/")
        self.assertEqual(res_missing.status_code, 428)

        res = self.client.post(
            f"/api/farmer/orders/{order.id}/accept/",
            HTTP_IF_MATCH=str(order.version),
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["status"], OrderStatus.ACCEPTED)

        self.product1.refresh_from_db()
        self.product2.refresh_from_db()
        self.assertEqual(self.product1.stock_quantity, 38)
        self.assertEqual(self.product2.stock_quantity, 19)

    def test_decline_order_api_with_mark_sold_out(self):
        order = self._create_order(farmer=self.farmer, status=OrderStatus.PLACED)
        self.client.force_authenticate(user=self.farmer_user)

        res = self.client.post(
            f"/api/farmer/orders/{order.id}/decline/",
            data={
                "reason": "Out of fresh basil today",
                "mark_sold_out_product_ids": [self.product2.id],
            },
            format="json",
            HTTP_IF_MATCH=str(order.version),
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["status"], OrderStatus.DECLINED)

        self.product2.refresh_from_db()
        self.assertEqual(self.product2.stock_quantity, 0)

    def test_ready_and_complete_order_api(self):
        order = self._create_order(farmer=self.farmer, status=OrderStatus.ACCEPTED)
        order.cutoff_at = timezone.now() - timedelta(minutes=5)
        order.save(update_fields=["cutoff_at"])

        self.client.force_authenticate(user=self.farmer_user)

        res_ready = self.client.post(
            f"/api/farmer/orders/{order.id}/ready/",
            HTTP_IF_MATCH=str(order.version),
        )
        self.assertEqual(res_ready.status_code, 200)
        self.assertEqual(res_ready.data["data"]["status"], OrderStatus.READY_FOR_PICKUP)
        order.refresh_from_db()

        res_comp = self.client.post(
            f"/api/farmer/orders/{order.id}/complete/",
            HTTP_IF_MATCH=str(order.version),
        )
        self.assertEqual(res_comp.status_code, 200)
        self.assertEqual(res_comp.data["data"]["status"], OrderStatus.COMPLETED)

    def test_no_show_order_api(self):
        order = self._create_order(
            farmer=self.farmer, status=OrderStatus.READY_FOR_PICKUP, is_overdue=True
        )
        initial_stock = self.product1.stock_quantity
        self.client.force_authenticate(user=self.farmer_user)

        res = self.client.post(
            f"/api/farmer/orders/{order.id}/no-show/",
            HTTP_IF_MATCH=str(order.version),
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["status"], OrderStatus.NO_SHOW)

        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock_quantity, initial_stock + 2)

    def test_approve_and_reject_change_request_api(self):
        order = self._create_order(farmer=self.farmer, status=OrderStatus.ACCEPTED, qty1=2, qty2=0)
        self.product1.stock_quantity -= 2
        self.product1.save(update_fields=["stock_quantity"])

        order.pending_change = {
            "items": [
                {
                    "product_id": self.product1.id,
                    "product_name": self.product1.name,
                    "quantity": 3,
                    "unit": self.product1.unit,
                    "unit_price": "4.00",
                }
            ],
            "pickup_date": None,
            "pickup_slot_id": None,
            "note": "Changed quantity",
            "change_summary": "Spinach: 2 -> 3",
            "requested_at": timezone.now().isoformat(),
        }
        order.save(update_fields=["pending_change"])

        self.client.force_authenticate(user=self.farmer_user)

        res_reject = self.client.post(
            f"/api/farmer/orders/{order.id}/change-request/reject/",
            data={"reason": "Cannot add more spinach today"},
            format="json",
            HTTP_IF_MATCH=str(order.version),
        )
        self.assertEqual(res_reject.status_code, 200)
        self.assertIsNone(res_reject.data["data"]["pending_change"])
        order.refresh_from_db()
        self.assertIsNone(order.pending_change)

        order.pending_change = {
            "items": [
                {
                    "product_id": self.product1.id,
                    "product_name": self.product1.name,
                    "quantity": 3,
                    "unit": self.product1.unit,
                    "unit_price": "4.00",
                }
            ],
            "pickup_date": None,
            "pickup_slot_id": None,
            "note": "Add 1 spinach",
            "change_summary": "Spinach: 2 -> 3",
            "requested_at": timezone.now().isoformat(),
        }
        order.save(update_fields=["pending_change"])

        res_approve = self.client.post(
            f"/api/farmer/orders/{order.id}/change-request/approve/",
            HTTP_IF_MATCH=str(order.version),
        )
        self.assertEqual(res_approve.status_code, 200)
        self.assertIsNone(res_approve.data["data"]["pending_change"])
        self.assertEqual(res_approve.data["data"]["total_amount"], "12.00")

    def test_picking_list_and_grouped_by_customer_api(self):
        order_a = self._create_order(farmer=self.farmer, status=OrderStatus.ACCEPTED, qty1=3, qty2=2)
        self._create_order(farmer=self.farmer, status=OrderStatus.READY_FOR_PICKUP, qty1=1, qty2=1)
        pickup_date = order_a.pickup_date.isoformat()

        self.client.force_authenticate(user=self.farmer_user)

        self.assertEqual(self.client.get("/api/farmer/orders/prep-list/").status_code, 404)

        res_pick = self.client.get(f"/api/farmer/orders/picking-list/?pickup_date={pickup_date}")
        self.assertEqual(res_pick.status_code, 200)
        coriander = next(r for r in res_pick.data["data"]["rows"] if r["product_id"] == self.product1.id)
        self.assertEqual(coriander["total_quantity"], 4)
        self.assertEqual(coriander["order_count"], 2)

        self.assertEqual(self.client.get("/api/farmer/orders/grouped-by-customer/").status_code, 400)
        res_grp = self.client.get(f"/api/farmer/orders/grouped-by-customer/?pickup_date={pickup_date}")
        self.assertEqual(res_grp.status_code, 200)
        grp_data = res_grp.data["data"]
        self.assertEqual(len(grp_data), 1)
        self.assertEqual(grp_data[0]["customer_id"], self.customer.id)
        self.assertEqual(grp_data[0]["order_count"], 2)
        self.assertEqual(grp_data[0]["total_amount"], "34.00")

    def test_bug1_non_existent_order_id_returns_404_not_500(self):
        self.client.force_authenticate(user=self.farmer_user)
        res = self.client.post(
            "/api/farmer/orders/999999/accept/",
            HTTP_IF_MATCH="1",
        )
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.data["code"], ErrorCode.NOT_FOUND)

    def test_bug6_other_farmer_order_returns_404_not_403_or_409(self):
        order = self._create_order(farmer=self.farmer, status=OrderStatus.PLACED)

        self.client.force_authenticate(user=self.other_farmer_user)

        res_wrong_version = self.client.post(
            f"/api/farmer/orders/{order.id}/accept/",
            HTTP_IF_MATCH="999",
        )
        self.assertEqual(res_wrong_version.status_code, 404)
        self.assertEqual(res_wrong_version.data["code"], ErrorCode.NOT_FOUND)

        res_matching_version = self.client.post(
            f"/api/farmer/orders/{order.id}/accept/",
            HTTP_IF_MATCH=str(order.version),
        )
        self.assertEqual(res_matching_version.status_code, 404)
        self.assertEqual(res_matching_version.data["code"], ErrorCode.NOT_FOUND)

    def test_bug2_decline_accepted_order_t4_with_mark_sold_out_stock_becomes_zero(self):
        self.product1.stock_quantity = 38
        self.product1.save(update_fields=["stock_quantity"])
        self.product2.stock_quantity = 19
        self.product2.save(update_fields=["stock_quantity"])
        order = self._create_order(farmer=self.farmer, status=OrderStatus.ACCEPTED, qty1=2, qty2=1)
        self.product1.refresh_from_db()
        self.product2.refresh_from_db()
        self.assertEqual(self.product1.stock_quantity, 38)
        self.assertEqual(self.product2.stock_quantity, 19)

        self.client.force_authenticate(user=self.farmer_user)

        res = self.client.post(
            f"/api/farmer/orders/{order.id}/decline/",
            data={
                "reason": "Product 1 is spoiled completely",
                "mark_sold_out_product_ids": [self.product1.id],
            },
            format="json",
            HTTP_IF_MATCH=str(order.version),
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["status"], OrderStatus.DECLINED)

        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock_quantity, 0)

        self.product2.refresh_from_db()
        self.assertEqual(self.product2.stock_quantity, 20)

    def test_bug3_and_chỗ_chưa_khớp_decline_validates_order_items(self):
        order = self._create_order(farmer=self.farmer, status=OrderStatus.PLACED)
        self.client.force_authenticate(user=self.farmer_user)

        unrelated_prod = Product.objects.create(
            review_status=ReviewStatus.APPROVED,
            farmer=self.farmer,
            category=self.category,
            name="Unrelated Melon",
            price=Decimal("10.00"),
            unit=Unit.EACH,
            stock_quantity=50,
        )

        res = self.client.post(
            f"/api/farmer/orders/{order.id}/decline/",
            data={
                "reason": "Declining order with invalid product ID",
                "mark_sold_out_product_ids": [unrelated_prod.id],
            },
            format="json",
            HTTP_IF_MATCH=str(order.version),
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["code"], ErrorCode.VALIDATION_ERROR)
        unrelated_prod.refresh_from_db()
        self.assertEqual(unrelated_prod.stock_quantity, 50)

        res_bool = self.client.post(
            f"/api/farmer/orders/{order.id}/decline/",
            data={
                "reason": "All items sold out",
                "mark_sold_out": True,
            },
            format="json",
            HTTP_IF_MATCH=str(order.version),
        )
        self.assertEqual(res_bool.status_code, 200)
        self.product1.refresh_from_db()
        self.product2.refresh_from_db()
        self.assertEqual(self.product1.stock_quantity, 0)
        self.assertEqual(self.product2.stock_quantity, 0)

    def test_bug5_pending_change_cleared_on_decline(self):
        order = self._create_order(farmer=self.farmer, status=OrderStatus.ACCEPTED)
        order.pending_change = {"items": [{"product_id": self.product1.id, "quantity": 10}]}
        order.save(update_fields=["pending_change"])

        self.client.force_authenticate(user=self.farmer_user)
        res = self.client.post(
            f"/api/farmer/orders/{order.id}/decline/",
            data={"reason": "Cannot fulfill this change", "mark_sold_out_product_ids": []},
            format="json",
            HTTP_IF_MATCH=str(order.version),
        )
        self.assertEqual(res.status_code, 200)
        order.refresh_from_db()
        self.assertIsNone(order.pending_change)

    def test_bug8_allowed_actions_excludes_accept_decline_past_pickup_start(self):
        order = self._create_order(farmer=self.farmer, status=OrderStatus.PLACED)
        past_time = timezone.now() - timedelta(minutes=10)
        order.cutoff_at = past_time - timedelta(hours=1)
        order.pickup_start_at = past_time
        order.pickup_end_at = past_time + timedelta(hours=2)
        order.save(update_fields=["cutoff_at", "pickup_start_at", "pickup_end_at"])

        self.client.force_authenticate(user=self.farmer_user)
        res = self.client.get(f"/api/farmer/orders/{order.id}/")
        self.assertEqual(res.status_code, 200)
        actions = res.data["data"]["allowed_actions"]
        self.assertNotIn("ACCEPT", actions)
        self.assertNotIn("DECLINE", actions)

    def test_fa20_standalone_tab_counts_endpoint(self):
        self.client.force_authenticate(user=self.farmer_user)
        res = self.client.get("/api/farmer/orders/tab-counts/")
        self.assertEqual(res.status_code, 200)
        data = res.data["data"]
        for key in ("placed", "accepted", "ready", "overdue", "change_requests", "by_date"):
            self.assertIn(key, data)

    def test_fa20_tab_counts_by_date_splits_open_orders_per_pickup_day(self):
        placed = self._create_order(farmer=self.farmer, status=OrderStatus.PLACED)
        self._create_order(farmer=self.farmer, status=OrderStatus.PLACED)
        self._create_order(farmer=self.farmer, status=OrderStatus.ACCEPTED)
        self._create_order(farmer=self.farmer, status=OrderStatus.COMPLETED)
        self._create_order(farmer=self.other_farmer, status=OrderStatus.PLACED)
        past = self._create_order(farmer=self.farmer, status=OrderStatus.ACCEPTED)
        past.pickup_date = timezone.localdate() - timedelta(days=1)
        past.save(update_fields=["pickup_date"])

        self.client.force_authenticate(user=self.farmer_user)
        by_date = self.client.get("/api/farmer/orders/tab-counts/").data["data"]["by_date"]

        self.assertEqual(by_date, {placed.pickup_date.isoformat(): {"placed": 2, "accepted": 1, "ready": 0}})

    def test_fa20_tab_counts_by_date_respects_market_filter(self):
        self._create_order(farmer=self.farmer, status=OrderStatus.PLACED)
        self.client.force_authenticate(user=self.farmer_user)

        res = self.client.get(f"/api/farmer/orders/tab-counts/?market_id={self.market.id + 999}")

        self.assertEqual(res.data["data"]["by_date"], {})
        self.assertEqual(res.data["data"]["placed"], 0)

    def test_fa21_picking_list_endpoint(self):
        self.client.force_authenticate(user=self.farmer_user)
        today_str = timezone.now().date().isoformat()
        res = self.client.get(f"/api/farmer/orders/picking-list/?pickup_date={today_str}")
        self.assertEqual(res.status_code, 200)
        self.assertIn("rows", res.data["data"])
        self.assertEqual(res.data["data"]["pickup_date"], today_str)

    def test_placed_order_accept_fails_when_stock_insufficient_and_declining_with_sold_out_sets_zero(self):
        order = self._create_order(farmer=self.farmer, status=OrderStatus.PLACED, qty1=5, qty2=2)

        self.product1.stock_quantity = 4
        self.product1.save(update_fields=["stock_quantity"])
        self.product2.stock_quantity = 20
        self.product2.save(update_fields=["stock_quantity"])

        self.client.force_authenticate(user=self.farmer_user)

        res_accept = self.client.post(
            f"/api/farmer/orders/{order.id}/accept/",
            HTTP_IF_MATCH=str(order.version),
        )
        self.assertEqual(res_accept.status_code, 400)
        self.assertEqual(res_accept.data["code"], ErrorCode.INSUFFICIENT_STOCK)
        self.assertIn(str(self.product1.id), res_accept.data["errors"])

        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.PLACED)
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock_quantity, 4)

        res_decline = self.client.post(
            f"/api/farmer/orders/{order.id}/decline/",
            data={
                "reason": "Only 4 bunches available, cannot fulfill full order",
                "mark_sold_out_product_ids": [self.product1.id],
            },
            format="json",
            HTTP_IF_MATCH=str(order.version),
        )
        self.assertEqual(res_decline.status_code, 200)
        self.assertEqual(res_decline.data["data"]["status"], OrderStatus.DECLINED)

        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock_quantity, 0)
        self.product2.refresh_from_db()
        self.assertEqual(self.product2.stock_quantity, 20)


    def test_other_farmer_invalid_transition_returns_404_not_400(self):
        order = self._create_order(farmer=self.farmer, status=OrderStatus.PLACED)
        self.client.force_authenticate(user=self.other_farmer_user)
        res = self.client.post(
            f"/api/farmer/orders/{order.id}/complete/",
            HTTP_IF_MATCH=str(order.version),
        )
        self.assertEqual(res.status_code, 404)
        self.assertEqual(res.data["code"], ErrorCode.NOT_FOUND)

    def test_allowed_actions_hide_change_actions_after_pickup_start(self):
        order = self._create_order(
            farmer=self.farmer,
            status=OrderStatus.ACCEPTED,
            pending_change={"items": [{"product_id": self.product1.id, "quantity": 3}]},
        )
        past = timezone.now() - timedelta(minutes=10)
        order.cutoff_at = past - timedelta(hours=1)
        order.pickup_start_at = past
        order.pickup_end_at = past + timedelta(hours=2)
        order.save(update_fields=["cutoff_at", "pickup_start_at", "pickup_end_at"])

        self.client.force_authenticate(user=self.farmer_user)
        actions = self.client.get(f"/api/farmer/orders/{order.id}/").data["data"]["allowed_actions"]
        for action in ("APPROVE_CHANGE", "REJECT_CHANGE", "DECLINE"):
            self.assertNotIn(action, actions)

    def test_decline_rejects_both_sold_out_fields(self):
        order = self._create_order(farmer=self.farmer, status=OrderStatus.PLACED)
        self.client.force_authenticate(user=self.farmer_user)
        res = self.client.post(
            f"/api/farmer/orders/{order.id}/decline/",
            data={
                "reason": "Out of stock today",
                "mark_sold_out": True,
                "mark_sold_out_product_ids": [self.product1.id],
            },
            format="json",
            HTTP_IF_MATCH=str(order.version),
        )
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["code"], ErrorCode.VALIDATION_ERROR)
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.PLACED)

    def test_t4_decline_requires_sold_out_declaration(self):
        order = self._create_order(farmer=self.farmer, status=OrderStatus.ACCEPTED, qty1=2, qty2=1)
        self.client.force_authenticate(user=self.farmer_user)

        res_missing = self.client.post(
            f"/api/farmer/orders/{order.id}/decline/",
            data={"reason": "Cannot prepare this order"},
            format="json",
            HTTP_IF_MATCH=str(order.version),
        )
        self.assertEqual(res_missing.status_code, 400)
        self.assertIn("mark_sold_out_product_ids", res_missing.data["errors"])
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.ACCEPTED)

        res_ok = self.client.post(
            f"/api/farmer/orders/{order.id}/decline/",
            data={"reason": "Cannot prepare this order", "mark_sold_out": False},
            format="json",
            HTTP_IF_MATCH=str(order.version),
        )
        self.assertEqual(res_ok.status_code, 200)
        self.product1.refresh_from_db()
        self.product2.refresh_from_db()
        self.assertEqual(self.product1.stock_quantity, 42)
        self.assertEqual(self.product2.stock_quantity, 21)

    def test_t3_decline_does_not_require_sold_out_declaration(self):
        order = self._create_order(farmer=self.farmer, status=OrderStatus.PLACED)
        self.client.force_authenticate(user=self.farmer_user)
        res = self.client.post(
            f"/api/farmer/orders/{order.id}/decline/",
            data={"reason": "Suspicious order"},
            format="json",
            HTTP_IF_MATCH=str(order.version),
        )
        self.assertEqual(res.status_code, 200)


    def _mark_item_url(self, order: Order, product: Product) -> str:
        return f"/api/farmer/orders/{order.id}/items/{product.id}/mark-sold-out/"

    def test_fa36_mark_item_sold_out_removes_item_and_notifies(self):
        order = self._create_order(farmer=self.farmer, status=OrderStatus.PLACED, qty1=2, qty2=1)
        self.client.force_authenticate(user=self.farmer_user)

        detail = self.client.get(f"/api/farmer/orders/{order.id}/").data["data"]
        self.assertIn("MARK_ITEM_SOLD_OUT", detail["allowed_actions"])

        res = self.client.post(self._mark_item_url(order, self.product2), HTTP_IF_MATCH=str(order.version))
        self.assertEqual(res.status_code, 200)
        data = res.data["data"]
        self.assertEqual(data["status"], OrderStatus.PLACED)
        self.assertEqual(data["version"], order.version + 1)
        self.assertEqual([item["product_id"] for item in data["items"]], [self.product1.id])
        self.assertEqual(data["total_amount"], "8.00")

        self.product2.refresh_from_db()
        self.assertEqual(self.product2.stock_quantity, 0)
        self.assertTrue(
            Notification.objects.filter(
                recipient=self.customer, type=NotificationType.ORDER_ITEM_SOLD_OUT
            ).exists()
        )
        history = OrderStatusHistory.objects.filter(order=order).order_by("-id").first()
        self.assertIsNone(history.transition)
        self.assertEqual(history.change_reason, "Farmer marked out of stock: Basil")

        res_accept = self.client.post(
            f"/api/farmer/orders/{order.id}/accept/", HTTP_IF_MATCH=str(data["version"])
        )
        self.assertEqual(res_accept.status_code, 200)
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock_quantity, 38)

    def test_fa36_only_item_cannot_be_removed(self):
        order = self._create_order(farmer=self.farmer, status=OrderStatus.PLACED, qty1=2, qty2=0)
        self.client.force_authenticate(user=self.farmer_user)
        res = self.client.post(self._mark_item_url(order, self.product1), HTTP_IF_MATCH=str(order.version))
        self.assertEqual(res.status_code, 400)
        self.product1.refresh_from_db()
        self.assertEqual(self.product1.stock_quantity, 40)

    def test_fa36_rejects_foreign_product_other_farmer_and_wrong_status(self):
        order = self._create_order(farmer=self.farmer, status=OrderStatus.PLACED)
        self.client.force_authenticate(user=self.farmer_user)

        other_product = Product.objects.create(
            review_status=ReviewStatus.APPROVED,
            farmer=self.farmer,
            category=self.category,
            name="Mint",
            unit=Unit.BUNCH,
            price=Decimal("3.00"),
            stock_quantity=10,
        )
        res = self.client.post(self._mark_item_url(order, other_product), HTTP_IF_MATCH=str(order.version))
        self.assertEqual(res.status_code, 404)

        res = self.client.post(self._mark_item_url(order, self.product1))
        self.assertEqual(res.status_code, 428)

        self.client.force_authenticate(user=self.other_farmer_user)
        res = self.client.post(self._mark_item_url(order, self.product1), HTTP_IF_MATCH=str(order.version))
        self.assertEqual(res.status_code, 404)

        accepted = self._create_order(farmer=self.farmer, status=OrderStatus.ACCEPTED)
        self.client.force_authenticate(user=self.farmer_user)
        res = self.client.post(self._mark_item_url(accepted, self.product1), HTTP_IF_MATCH=str(accepted.version))
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.data["code"], ErrorCode.FAILED_PRECONDITION)


    def test_order_detail_presents_pending_change(self):
        order = self._create_order(farmer=self.farmer, status=OrderStatus.ACCEPTED, qty1=2, qty2=0)
        order.pending_change = {
            "items": [{"product_id": self.product1.id, "quantity": 3, "unit_price": "4.00"}],
            "pickup_date": None,
            "pickup_slot_id": None,
            "note": "Add one bunch",
            "requested_at": timezone.now().isoformat(),
            "change_summary": "Coriander 2->3",
        }
        order.save(update_fields=["pending_change"])

        self.client.force_authenticate(user=self.farmer_user)
        pending = self.client.get(f"/api/farmer/orders/{order.id}/").data["data"]["pending_change"]
        self.assertEqual(pending["estimated_total"], "12.00")
        self.assertEqual(pending["note"], "Add one bunch")
        self.assertIsNotNone(pending["expires_at"])
        self.assertIsNone(pending["pickup_start_at"])
        self.assertNotIn("change_summary", pending)
        item = pending["items"][0]
        self.assertEqual(item["product_id"], self.product1.id)
        self.assertEqual(item["product_name"], "Coriander")
        self.assertEqual(item["quantity"], 3)
        self.assertEqual(item["current_quantity"], 2)
        self.assertEqual(item["stock_available"], 40)



    def test_list_rejects_invalid_parameters(self):
        self.client.force_authenticate(user=self.farmer_user)
        for query in (
            "tab=CONFIRMED",
            "status=UNKNOWN",
            "market_id=abc",
            "pickup_from=2026-13-01",
            "pickup_from=2026-10-05&pickup_to=2026-10-01",
            "overdue=maybe",
            "tab=history&ordering=pickup_start_at",
            "ordering=price",
        ):
            res = self.client.get(f"/api/farmer/orders/?{query}")
            self.assertEqual(res.status_code, 400, query)
            self.assertEqual(res.data["code"], ErrorCode.VALIDATION_ERROR, query)

    def test_list_filters_status_dates_q_and_overdue(self):
        declined = self._create_order(farmer=self.farmer, status=OrderStatus.DECLINED)
        self._create_order(farmer=self.farmer, status=OrderStatus.COMPLETED)
        overdue = self._create_order(farmer=self.farmer, status=OrderStatus.ACCEPTED, is_overdue=True)
        self._create_order(farmer=self.farmer, status=OrderStatus.ACCEPTED)
        self.client.force_authenticate(user=self.farmer_user)

        res = self.client.get("/api/farmer/orders/?tab=history&status=DECLINED")
        self.assertEqual([o["id"] for o in res.data["data"]["results"]], [declined.id])

        res = self.client.get("/api/farmer/orders/?tab=accepted&overdue=true")
        self.assertEqual([o["id"] for o in res.data["data"]["results"]], [overdue.id])

        day = overdue.pickup_date.isoformat()
        res = self.client.get(f"/api/farmer/orders/?tab=accepted&pickup_from={day}&pickup_to={day}")
        self.assertEqual([o["id"] for o in res.data["data"]["results"]], [overdue.id])

        res = self.client.get(f"/api/farmer/orders/?tab=history&q={declined.id}")
        self.assertEqual([o["id"] for o in res.data["data"]["results"]], [declined.id])
        res = self.client.get("/api/farmer/orders/?tab=history&q=bui")
        self.assertEqual(len(res.data["data"]["results"]), 2)

        counts = self.client.get("/api/farmer/orders/tab-counts/").data["data"]
        self.assertEqual(counts["overdue"], 1)

    def test_placed_tab_can_sort_by_pickup_time_and_flags_expiring_soon(self):
        later = self._create_order(farmer=self.farmer, status=OrderStatus.PLACED)
        soon = self._create_order(farmer=self.farmer, status=OrderStatus.PLACED)
        now = timezone.now()
        soon.cutoff_at = now - timedelta(hours=1)
        soon.pickup_start_at = now + timedelta(hours=1)
        soon.pickup_end_at = now + timedelta(hours=3)
        soon.save(update_fields=["cutoff_at", "pickup_start_at", "pickup_end_at"])
        self.client.force_authenticate(user=self.farmer_user)

        default = self.client.get("/api/farmer/orders/?tab=placed").data["data"]["results"]
        self.assertEqual([o["id"] for o in default], [later.id, soon.id])

        by_pickup = self.client.get("/api/farmer/orders/?tab=placed&ordering=pickup_start_at").data["data"]["results"]
        self.assertEqual([o["id"] for o in by_pickup], [soon.id, later.id])
        flags = {o["id"]: o["is_expiring_soon"] for o in by_pickup}
        self.assertTrue(flags[soon.id])
        self.assertFalse(flags[later.id])

    def test_stock_warning_uses_current_stock_only(self):
        ok_order = self._create_order(farmer=self.farmer, status=OrderStatus.PLACED, qty1=1, qty2=6)
        short_order = self._create_order(farmer=self.farmer, status=OrderStatus.PLACED, qty1=1, qty2=25)
        self.client.force_authenticate(user=self.farmer_user)
        results = self.client.get("/api/farmer/orders/?tab=placed").data["data"]["results"]
        warnings = {o["id"]: o["stock_warning"] for o in results}
        self.assertFalse(warnings[ok_order.id])
        self.assertTrue(warnings[short_order.id])

    def test_picking_list_requires_valid_pickup_date(self):
        self.client.force_authenticate(user=self.farmer_user)
        self.assertEqual(self.client.get("/api/farmer/orders/picking-list/").status_code, 400)
        self.assertEqual(
            self.client.get("/api/farmer/orders/picking-list/?pickup_date=26-09-2026").status_code, 400
        )

    def test_order_summary_and_detail_shape(self):
        order = self._create_order(farmer=self.farmer, status=OrderStatus.PLACED)
        self.client.force_authenticate(user=self.farmer_user)

        summary = self.client.get("/api/farmer/orders/?tab=placed").data["data"]["results"][0]
        for key in (
            "id", "status", "is_overdue", "is_expiring_soon", "has_pending_change", "version",
            "customer", "farmer", "market", "stall_label", "pickup_date", "pickup_start_at",
            "pickup_end_at", "cutoff_at", "item_count", "total_amount", "stock_warning", "created_at",
        ):
            self.assertIn(key, summary)
        self.assertEqual(summary["customer"], {"id": self.customer.id, "full_name": "Bui Customer", "phone": "0911555666"})
        self.assertEqual(summary["farmer"]["stall_name"], "Highland Greenery")
        self.assertIn("latitude", summary["market"])
        self.assertEqual(summary["item_count"], 2)

        detail = self.client.get(f"/api/farmer/orders/{order.id}/").data["data"]
        self.assertEqual(detail["customer"]["email"], self.customer.email)
        self.assertEqual(detail["pickup_slot_id"], self.slot.id)
        self.assertNotIn("pickup_slot", detail)
        self.assertIn("product_image", detail["items"][0])
        placed_row = detail["status_history"][0]
        self.assertEqual(placed_row["actor_name"], "Bui Customer")

    def test_status_history_translates_system_codes(self):
        order = self._create_order(farmer=self.farmer, status=OrderStatus.PLACED, is_overdue=True)
        self.client.force_authenticate(user=self.farmer_user)
        self.client.get("/api/farmer/orders/?tab=history")
        detail = self.client.get(f"/api/farmer/orders/{order.id}/").data["data"]
        expired_row = detail["status_history"][-1]
        self.assertEqual(expired_row["transition"], "T8")
        self.assertIsNone(expired_row["actor_name"])
        self.assertEqual(expired_row["change_reason"], "The order was not confirmed before the pickup time.")
