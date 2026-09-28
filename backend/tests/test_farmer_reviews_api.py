from datetime import datetime, time, timedelta
from decimal import Decimal

from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.models import CustomUser, CustomerProfile, FarmerProfile, FarmerStatus, Role, RoleCode
from catalog.models import Category, Product, Unit
from marketlink_core.exceptions import ErrorCode
from markets.models import Market
from orders.models import Order, OrderItem, OrderStatus
from reviews.models import FarmerReview, ProductReview
from reviews.selectors import customer_display_name

LIST_URL = "/api/farmer/reviews/"
REVIEW_KEYS = {
    "id", "type", "rating", "comment", "customer_display_name", "product", "order_id",
    "reply", "replied_at", "is_hidden_by_admin", "hidden_reason", "created_at",
}


class CustomerDisplayNameTestCase(SimpleTestCase):
    def test_u05_short_name(self):
        self.assertEqual(customer_display_name("Nguyen Van A"), "Nguyen V. A.")
        self.assertEqual(customer_display_name("  le  thi   hoa "), "le T. H.")
        self.assertEqual(customer_display_name("Mai"), "Mai")
        self.assertEqual(customer_display_name(""), "Customer")


class FarmerReviewsAPITestCase(TestCase):
    """F9: FA-28 -> FA-30 (D-016, U-05, decision D5 v1.8)."""

    def setUp(self):
        self.client = APIClient()
        farmer_role, _ = Role.objects.get_or_create(code=RoleCode.FARMER, defaults={"name": "Farmer"})
        customer_role, _ = Role.objects.get_or_create(code=RoleCode.CUSTOMER, defaults={"name": "Customer"})
        self.farmer_user = CustomUser.objects.create(email="rev_farmer@marketlink.local", role=farmer_role)
        self.farmer = FarmerProfile.objects.create(
            user=self.farmer_user,
            stall_name="Review Stall",
            contact_person="Rev Farmer",
            phone="0944100100",
            address="1 Review Road",
            status=FarmerStatus.APPROVED,
            operating_days=[1, 2, 3, 4, 5, 6, 7],
        )
        other_user = CustomUser.objects.create(email="rev_other@marketlink.local", role=farmer_role)
        self.other_farmer = FarmerProfile.objects.create(
            user=other_user,
            stall_name="Other Review",
            contact_person="Other",
            phone="0944100200",
            address="2 Review Road",
            operating_days=[1],
        )
        self.customer = CustomUser.objects.create(email="rev_customer@marketlink.local", role=customer_role)
        CustomerProfile.objects.create(user=self.customer, full_name="Nguyen Van An", phone="0911500100", address="3 Road")
        self.market = Market.objects.create(
            name="Review Market",
            address="Market address",
            latitude=Decimal("10.770000"),
            longitude=Decimal("106.700000"),
            open_time="05:00",
            close_time="20:00",
        )
        category = Category.objects.create(name="Herbs")
        self.basil = Product.objects.create(
            farmer=self.farmer, category=category, name="Basil", unit=Unit.KG, price=Decimal("2.00"), stock_quantity=5
        )
        self.other_mint = Product.objects.create(
            farmer=self.other_farmer, category=category, name="Mint", unit=Unit.KG, price=Decimal("2.00"), stock_quantity=5
        )

        base = timezone.now() - timedelta(days=5)
        order1 = self._order(self.farmer, [self.basil])
        order2 = self._order(self.farmer, [self.basil])
        other_order = self._order(self.other_farmer, [self.other_mint])
        self.stall_review = self._review(FarmerReview, base, order=order1, rating=5, comment="Great stall")
        self.hidden_review = self._review(
            ProductReview, base + timedelta(hours=1), order_item=order1.items.first(), rating=2,
            is_hidden_by_admin=True, hidden_reason="Spam",
        )
        self.replied_review = self._review(
            FarmerReview, base + timedelta(hours=2), order=order2, rating=3, reply="Thanks!", replied_at=base
        )
        self.basil_review = self._review(ProductReview, base + timedelta(hours=3), order_item=order2.items.first(), rating=4)
        self.other_review = self._review(FarmerReview, base, order=other_order, rating=1)
        self.client.force_authenticate(user=self.farmer_user)

    def _order(self, farmer, products) -> Order:
        pickup_date = timezone.localdate() - timedelta(days=6)
        start_at = timezone.make_aware(datetime.combine(pickup_date, time(8, 0)), timezone.get_current_timezone())
        order = Order.objects.create(
            customer=self.customer,
            farmer=farmer,
            market=self.market,
            stall_label="R1",
            pickup_date=pickup_date,
            pickup_start_at=start_at,
            pickup_end_at=start_at + timedelta(hours=2),
            cutoff_at=start_at - timedelta(hours=12),
            total_amount=Decimal("2.00") * len(products),
            status=OrderStatus.COMPLETED,
        )
        for product in products:
            OrderItem.objects.create(
                order=order, product=product, product_name=product.name, unit=product.unit,
                unit_price=Decimal("2.00"), quantity=1, line_total=Decimal("2.00"),
            )
        return order

    def _review(self, model, created_at, **fields):
        review = model.objects.create(**fields)
        model.objects.filter(pk=review.pk).update(created_at=created_at)
        review.refresh_from_db()
        return review

    def _list(self, **params):
        res = self.client.get(LIST_URL, params)
        self.assertEqual(res.status_code, 200, res.data)
        return res.data["data"]


    def test_list_merges_both_types_newest_first(self):
        data = self._list()
        self.assertEqual(data["count"], 4)
        rows = data["results"]
        self.assertEqual(
            [(row["type"], row["id"]) for row in rows],
            [
                ("PRODUCT", self.basil_review.pk),
                ("FARMER", self.replied_review.pk),
                ("PRODUCT", self.hidden_review.pk),
                ("FARMER", self.stall_review.pk),
            ],
        )
        self.assertEqual(set(rows[0]), REVIEW_KEYS)
        self.assertEqual(rows[0]["product"], {"id": self.basil.pk, "name": "Basil"})
        self.assertIsNone(rows[1]["product"])
        self.assertEqual(rows[0]["customer_display_name"], "Nguyen V. A.")

    def test_hidden_review_is_flagged_without_reason(self):
        hidden = next(row for row in self._list()["results"] if row["id"] == self.hidden_review.pk and row["type"] == "PRODUCT")
        self.assertTrue(hidden["is_hidden_by_admin"])
        self.assertIsNone(hidden["hidden_reason"])

    def test_filters(self):
        self.assertEqual(self._list(type="farmer")["count"], 2)
        self.assertEqual(self._list(type="PRODUCT")["count"], 2)
        self.assertEqual([row["rating"] for row in self._list(rating=4)["results"]], [4])
        self.assertEqual([row["id"] for row in self._list(replied="true")["results"]], [self.replied_review.pk])
        self.assertEqual(self._list(replied="false", type="FARMER")["count"], 1)

    def test_pagination(self):
        data = self._list(page_size=5, page=1)
        self.assertEqual((data["count"], data["total_pages"]), (4, 1))

    def test_invalid_filters(self):
        for params, field in (({"type": "SHOP"}, "type"), ({"rating": 6}, "rating"), ({"replied": "yes"}, "replied")):
            with self.subTest(params=params):
                res = self.client.get(LIST_URL, params)
                self.assertEqual(res.status_code, 400)
                self.assertIn(field, res.data["errors"])


    def test_reply_to_stall_review(self):
        res = self.client.post(f"/api/farmer/farmer-reviews/{self.stall_review.pk}/reply/", {"reply": "  Thank you!  "}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["reply"], "Thank you!")
        self.assertIsNotNone(res.data["data"]["replied_at"])
        self.stall_review.refresh_from_db()
        self.assertEqual(self.stall_review.reply, "Thank you!")

    def test_reply_to_product_review(self):
        res = self.client.post(f"/api/farmer/product-reviews/{self.basil_review.pk}/reply/", {"reply": "Glad you liked it"}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["type"], "PRODUCT")

    def test_reply_only_once(self):
        res = self.client.post(f"/api/farmer/farmer-reviews/{self.replied_review.pk}/reply/", {"reply": "Again"}, format="json")
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.data["code"], ErrorCode.REPLY_ALREADY_EXISTS)
        self.replied_review.refresh_from_db()
        self.assertEqual(self.replied_review.reply, "Thanks!")

    def test_hidden_review_cannot_be_replied(self):
        res = self.client.post(f"/api/farmer/product-reviews/{self.hidden_review.pk}/reply/", {"reply": "Hi"}, format="json")
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.data["code"], ErrorCode.FAILED_PRECONDITION)

    def test_reply_scope_and_type_must_match(self):
        other = self.client.post(f"/api/farmer/farmer-reviews/{self.other_review.pk}/reply/", {"reply": "Hi"}, format="json")
        self.assertEqual(other.status_code, 404)
        missing = self.client.post("/api/farmer/farmer-reviews/999999/reply/", {"reply": "Hi"}, format="json")
        self.assertEqual(missing.status_code, 404)
        other_product = ProductReview.objects.create(
            order_item=self._order(self.other_farmer, [self.other_mint]).items.first(), rating=5
        )
        res = self.client.post(f"/api/farmer/product-reviews/{other_product.pk}/reply/", {"reply": "Hi"}, format="json")
        self.assertEqual(res.status_code, 404)

    def test_reply_length(self):
        url = f"/api/farmer/farmer-reviews/{self.stall_review.pk}/reply/"
        for body in ({"reply": "   "}, {"reply": "x" * 501}, {}):
            with self.subTest(body=body):
                res = self.client.post(url, body, format="json")
                self.assertEqual(res.status_code, 400)
                self.assertIn("reply", res.data["errors"])

    def test_suspended_farmer_cannot_reply_but_can_read(self):
        FarmerProfile.objects.filter(pk=self.farmer.pk).update(status=FarmerStatus.SUSPENDED)
        res = self.client.post(f"/api/farmer/farmer-reviews/{self.stall_review.pk}/reply/", {"reply": "Hi"}, format="json")
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["code"], ErrorCode.FARMER_SUSPENDED)
        self.assertEqual(self._list()["count"], 4)

    def test_customer_is_forbidden(self):
        self.client.force_authenticate(user=self.customer)
        self.assertEqual(self.client.get(LIST_URL).status_code, 403)
