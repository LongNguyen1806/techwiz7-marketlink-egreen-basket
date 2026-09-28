import io
from datetime import date, time, timedelta
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile
from unittest import mock

from django.test import TestCase
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from accounts.models import (
    CustomUser,
    CustomerProfile,
    FarmerProfile,
    FarmerStatus,
    Role,
    RoleCode,
)
from catalog.models import Category, Product, ProductMarket, ReviewStatus, Unit
from favorites.models import FavoriteProduct
from marketlink_core.exceptions import ErrorCode
from markets.models import FarmerMarket, Market, PickupSlot
from notifications.models import Notification, NotificationType
from orders.models import Order, OrderItem, OrderStatus


def create_test_image(format="JPEG", size=(50, 50), color=(255, 0, 0)) -> bytes:
    img_byte_arr = io.BytesIO()
    image = Image.new("RGB", size, color)
    image.save(img_byte_arr, format=format)
    return img_byte_arr.getvalue()


class FarmerProductsAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()

        self.farmer_role, _ = Role.objects.get_or_create(
            code=RoleCode.FARMER, defaults={"name": "Farmer"}
        )
        self.customer_role, _ = Role.objects.get_or_create(
            code=RoleCode.CUSTOMER, defaults={"name": "Customer"}
        )

        self.farmer_user = CustomUser.objects.create(
            email="farmer1@marketlink.local",
            role=self.farmer_role,
        )
        self.farmer_profile = FarmerProfile.objects.create(
            user=self.farmer_user,
            stall_name="Green Garden",
            contact_person="Farmer John",
            phone="0901234567",
            address="Valley 1",
            status=FarmerStatus.APPROVED,
            order_cutoff_hours=12,
            operating_days=[1, 2, 3, 4, 5, 6, 7],
        )
        self.home_market = Market.objects.create(
            name="Home Market",
            address="9 Home Street",
            latitude=Decimal("10.7"),
            longitude=Decimal("106.6"),
            open_time=time(6, 0),
            close_time=time(12, 0),
        )
        self.home_stall = FarmerMarket.objects.create(
            farmer=self.farmer_profile, market=self.home_market, stall_label="Home row, Stall 1"
        )

        self.pending_farmer_user = CustomUser.objects.create(
            email="farmer_pending@marketlink.local",
            role=self.farmer_role,
        )
        self.pending_farmer_profile = FarmerProfile.objects.create(
            user=self.pending_farmer_user,
            stall_name="Pending Farm",
            contact_person="Pending Pete",
            phone="0901112233",
            address="Valley 2",
            status=FarmerStatus.PENDING,
            order_cutoff_hours=12,
            operating_days=[1, 2, 3],
        )

        self.customer_user = CustomUser.objects.create(
            email="customer1@marketlink.local",
            role=self.customer_role,
        )
        self.customer_profile = CustomerProfile.objects.create(
            user=self.customer_user,
            full_name="Alice Customer",
            phone="0911222333",
            address="City Center",
        )

        self.category = Category.objects.create(name="Vegetables", is_active=True)

        self.prod1 = Product.objects.create(
            review_status=ReviewStatus.APPROVED,
            farmer=self.farmer_profile,
            category=self.category,
            name="Organic Tomato",
            price=Decimal("3.50"),
            unit=Unit.KG,
            stock_quantity=20,
            weekly_default_quantity=25,
            is_available=True,
        )
        self.prod2 = Product.objects.create(
            review_status=ReviewStatus.APPROVED,
            farmer=self.farmer_profile,
            category=self.category,
            name="Fresh Carrot",
            price=Decimal("2.00"),
            unit=Unit.KG,
            stock_quantity=0,
            weekly_default_quantity=15,
            is_available=True,
        )
        for product in (self.prod1, self.prod2):
            ProductMarket.objects.create(product=product, farmer_market=self.home_stall)

    def test_fa11_list_products_and_stock_quantities(self):
        self.client.force_authenticate(user=self.farmer_user)

        now = timezone.now()
        market = Market.objects.create(
            name="Downtown Market",
            address="Main St",
            latitude=Decimal("10.0"),
            longitude=Decimal("106.0"),
            open_time=time(6, 0),
            close_time=time(18, 0),
            is_active=True,
        )
        fm = FarmerMarket.objects.create(
            farmer=self.farmer_profile,
            market=market,
            stall_label="Stall 1",
        )
        ProductMarket.objects.create(product=self.prod1, farmer_market=fm)
        slot = PickupSlot.objects.create(
            farmer_market=fm,
            day_of_week=1,
            start_time=time(8, 0),
            end_time=time(12, 0),
            is_active=True,
        )
        order = Order.objects.create(
            customer=self.customer_user,
            farmer=self.farmer_profile,
            market=market,
            pickup_slot=slot,
            pickup_date=(now + timedelta(hours=2)).date(),
            pickup_start_at=now + timedelta(hours=2),
            pickup_end_at=now + timedelta(hours=4),
            cutoff_at=now + timedelta(hours=1),
            status=OrderStatus.PLACED,
            total_amount=Decimal("17.50"),
        )
        OrderItem.objects.create(
            order=order,
            product=self.prod1,
            product_name="Organic Tomato",
            unit=Unit.KG,
            unit_price=Decimal("3.50"),
            quantity=5,
            line_total=Decimal("17.50"),
        )

        res = self.client.get("/api/farmer/products/")
        self.assertEqual(res.status_code, 200)
        items = res.data["data"]["results"]
        self.assertEqual(len(items), 2)

        tomato_item = next(i for i in items if i["id"] == self.prod1.id)
        self.assertEqual(tomato_item["stock_quantity"], 20)
        self.assertEqual(tomato_item["pending_quantity"], 5)
        self.assertEqual(tomato_item["held_quantity"], 0)
        self.assertNotIn("available_stock", tomato_item)
        self.assertEqual(
            tomato_item["markets"],
            [
                {"market_id": market.id, "market_name": "Downtown Market", "days": [1]},
                {"market_id": self.home_market.id, "market_name": "Home Market", "days": []},
            ],
        )

    def test_fa11_filtering_by_state(self):
        self.client.force_authenticate(user=self.farmer_user)

        res_in_stock = self.client.get("/api/farmer/products/?state=in_stock")
        self.assertEqual(len(res_in_stock.data["data"]["results"]), 1)
        self.assertEqual(res_in_stock.data["data"]["results"][0]["id"], self.prod1.id)

        res_out = self.client.get("/api/farmer/products/?state=out_of_stock")
        self.assertEqual(len(res_out.data["data"]["results"]), 1)
        self.assertEqual(res_out.data["data"]["results"][0]["id"], self.prod2.id)

    def test_fa12_create_product_approved_vs_pending(self):
        self.client.force_authenticate(user=self.pending_farmer_user)
        payload = {
            "name": "Sweet Corn",
            "category_id": self.category.id,
            "price": "4.00",
            "unit": Unit.EACH,
            "stock_quantity": 30,
        }
        res_pending = self.client.post("/api/farmer/products/", payload)
        self.assertEqual(res_pending.status_code, 403)
        self.assertEqual(res_pending.data["code"], ErrorCode.FARMER_NOT_APPROVED)

        self.client.force_authenticate(user=self.farmer_user)
        res_approved = self.client.post("/api/farmer/products/", payload)
        self.assertEqual(res_approved.status_code, 201)
        self.assertEqual(res_approved.data["data"]["name"], "Sweet Corn")
        self.assertEqual(res_approved.data["data"]["stock_quantity"], 30)

    def test_fa12_ct18_disguised_executable_rejected(self):
        self.client.force_authenticate(user=self.farmer_user)

        fake_image = SimpleUploadedFile(
            name="malicious.jpg",
            content=b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00This is a fake PE executable",
            content_type="image/jpeg",
        )
        payload = {
            "name": "Hacked Product",
            "category_id": self.category.id,
            "price": "5.00",
            "unit": Unit.KG,
            "stock_quantity": 10,
            "image": fake_image,
        }
        res = self.client.post("/api/farmer/products/", payload, format="multipart")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["code"], ErrorCode.VALIDATION_ERROR)

    def test_fa13_get_detail_and_isolation(self):
        self.client.force_authenticate(user=self.farmer_user)
        res = self.client.get(f"/api/farmer/products/{self.prod1.id}/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["name"], self.prod1.name)

        self.client.force_authenticate(user=self.pending_farmer_user)
        res_other = self.client.get(f"/api/farmer/products/{self.prod1.id}/")
        self.assertEqual(res_other.status_code, 404)

    def test_fa14_patch_restock_alert_d025(self):
        self.client.force_authenticate(user=self.farmer_user)

        FavoriteProduct.objects.create(customer=self.customer_user, product=self.prod2)

        res = self.client.patch(
            f"/api/farmer/products/{self.prod2.id}/",
            {"stock_quantity": 10},
            format="json",
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["stock_quantity"], 10)
        self.assertEqual(res.data["data"]["restock_notified"], 1)

        notif = Notification.objects.filter(
            recipient=self.customer_user,
            type=NotificationType.RESTOCK,
        ).first()
        self.assertIsNotNone(notif)
        self.assertIn("Fresh Carrot", notif.title)

    def test_fa15_soft_delete_and_fa16_mark_sold_out(self):
        self.client.force_authenticate(user=self.farmer_user)

        res_sold_out = self.client.post(f"/api/farmer/products/{self.prod1.id}/mark-sold-out/")
        self.assertEqual(res_sold_out.status_code, 200)
        self.prod1.refresh_from_db()
        self.assertEqual(self.prod1.stock_quantity, 0)

        res_delete = self.client.delete(f"/api/farmer/products/{self.prod1.id}/")
        self.assertEqual(res_delete.status_code, 204)
        self.prod1.refresh_from_db()
        self.assertTrue(self.prod1.is_archived)

    def test_fa17_and_fa18_weekly_template(self):
        self.client.force_authenticate(user=self.farmer_user)

        res_preview = self.client.get("/api/farmer/products/weekly-template-preview/")
        self.assertEqual(res_preview.status_code, 200)
        rows = res_preview.data["data"]["rows"]
        self.assertEqual(len(rows), 2)

        row_tomato = next(r for r in rows if r["product_id"] == self.prod1.id)
        self.assertEqual(row_tomato["new_stock"], 25)

        FavoriteProduct.objects.create(customer=self.customer_user, product=self.prod2)

        res_apply = self.client.post("/api/farmer/products/apply-weekly-template/", {})
        self.assertEqual(res_apply.status_code, 200)
        self.assertEqual(res_apply.data["data"]["updated_count"], 2)
        self.assertEqual(res_apply.data["data"]["restock_notified"], 1)

        self.prod1.refresh_from_db()
        self.prod2.refresh_from_db()
        self.assertEqual(self.prod1.stock_quantity, 25)
        self.assertEqual(self.prod2.stock_quantity, 15)


    def test_suspended_farmer_cannot_write_products(self):
        self.farmer_profile.status = FarmerStatus.SUSPENDED
        self.farmer_profile.save(update_fields=["status"])
        self.client.force_authenticate(user=self.farmer_user)
        payload = {
            "name": "Sweet Corn",
            "category_id": self.category.id,
            "price": "4.00",
            "unit": Unit.EACH,
            "stock_quantity": 30,
        }
        responses = [
            self.client.post("/api/farmer/products/", payload),
            self.client.patch(f"/api/farmer/products/{self.prod1.id}/", {"name": "New name"}, format="json"),
            self.client.delete(f"/api/farmer/products/{self.prod1.id}/"),
            self.client.post(f"/api/farmer/products/{self.prod1.id}/mark-sold-out/"),
        ]
        for res in responses:
            self.assertEqual(res.status_code, 403)
            self.assertEqual(res.data["code"], ErrorCode.FARMER_SUSPENDED)
        self.assertEqual(self.client.get("/api/farmer/products/").status_code, 200)
        self.prod1.refresh_from_db()
        self.assertEqual(self.prod1.stock_quantity, 20)
        self.assertFalse(self.prod1.is_archived)

    def test_list_rejects_invalid_filters(self):
        self.client.force_authenticate(user=self.farmer_user)
        for query in ("category_id=abc", "category_id=0", "state=unknown"):
            res = self.client.get(f"/api/farmer/products/?{query}")
            self.assertEqual(res.status_code, 400, query)
            self.assertEqual(res.data["code"], ErrorCode.VALIDATION_ERROR, query)

    def _create_with_image(self, upload: SimpleUploadedFile):
        payload = {
            "name": "Photo Product",
            "category_id": self.category.id,
            "price": "5.00",
            "unit": Unit.KG,
            "stock_quantity": 10,
            "image": upload,
        }
        return self.client.post("/api/farmer/products/", payload, format="multipart")

    def test_image_extension_and_mime_are_checked(self):
        self.client.force_authenticate(user=self.farmer_user)
        res = self._create_with_image(
            SimpleUploadedFile("page.html", create_test_image("JPEG"), content_type="image/jpeg")
        )
        self.assertEqual(res.status_code, 400)
        res = self._create_with_image(
            SimpleUploadedFile("photo.jpg", create_test_image("JPEG"), content_type="text/html")
        )
        self.assertEqual(res.status_code, 400)

    def test_stored_extension_follows_real_image_format(self):
        self.client.force_authenticate(user=self.farmer_user)
        res = self._create_with_image(
            SimpleUploadedFile("Holiday.JPG", create_test_image("PNG"), content_type="image/jpeg")
        )
        self.assertEqual(res.status_code, 201)
        product = Product.objects.get(id=res.data["data"]["id"])
        self.assertTrue(product.image.name.startswith("products/"))
        self.assertTrue(product.image.name.endswith(".png"))
        self.assertNotIn("Holiday", product.image.name)
        product.image.delete(save=False)

    def test_removing_the_photo_clears_it_and_sends_the_listing_back_for_review(self):
        self.prod1.image.save("tomato.png", io.BytesIO(create_test_image("PNG")), save=True)
        stored = self.prod1.image.name
        self.client.force_authenticate(user=self.farmer_user)

        res = self.client.patch(f"/api/farmer/products/{self.prod1.id}/", {"image": None}, format="json")

        self.prod1.image.storage.delete(stored)
        self.assertEqual(res.status_code, 200)
        self.assertIsNone(res.data["data"]["image"])
        self.assertTrue(res.data["data"]["sent_for_review"])
        self.prod1.refresh_from_db()
        self.assertFalse(self.prod1.image)
        self.assertEqual(self.prod1.review_status, ReviewStatus.PENDING)

    def test_farmer_product_shape_and_held_quantity(self):
        now = timezone.now()
        market = Market.objects.create(
            name="Riverside Market",
            address="River Rd",
            latitude=Decimal("10.0"),
            longitude=Decimal("106.0"),
            open_time=time(6, 0),
            close_time=time(18, 0),
            is_active=True,
        )
        fm = FarmerMarket.objects.create(farmer=self.farmer_profile, market=market, stall_label="R1")
        ProductMarket.objects.create(product=self.prod1, farmer_market=fm)
        slot = PickupSlot.objects.create(
            farmer_market=fm, day_of_week=3, start_time=time(8, 0), end_time=time(10, 0), is_active=True
        )
        order = Order.objects.create(
            customer=self.customer_user,
            farmer=self.farmer_profile,
            market=market,
            pickup_slot=slot,
            pickup_date=(now - timedelta(days=1)).date(),
            pickup_start_at=now - timedelta(days=1),
            pickup_end_at=now - timedelta(days=1) + timedelta(hours=2),
            cutoff_at=now - timedelta(days=2),
            status=OrderStatus.ACCEPTED,
            total_amount=Decimal("7.00"),
        )
        OrderItem.objects.create(
            order=order,
            product=self.prod1,
            product_name=self.prod1.name,
            unit=Unit.KG,
            unit_price=Decimal("3.50"),
            quantity=2,
            line_total=Decimal("7.00"),
        )
        self.client.force_authenticate(user=self.farmer_user)
        data = self.client.get(f"/api/farmer/products/{self.prod1.id}/").data["data"]
        for key in (
            "availability", "farmer", "rating_avg", "rating_count", "is_favorite", "markets",
            "held_quantity", "pending_quantity", "weekly_default_quantity", "is_archived",
            "is_hidden_by_admin", "hidden_reason", "category",
        ):
            self.assertIn(key, data)
        self.assertNotIn("category_id", data)
        self.assertEqual(data["held_quantity"], 2)
        self.assertEqual(data["availability"], "IN_STOCK")
        self.assertEqual(data["farmer"], {"id": self.farmer_profile.pk, "stall_name": "Green Garden"})
        self.assertIsNone(data["rating_avg"])
        self.assertEqual(data["rating_count"], 0)
        self.assertEqual(
            data["markets"],
            [
                {"market_id": self.home_market.id, "market_name": "Home Market", "days": []},
                {"market_id": market.id, "market_name": "Riverside Market", "days": [3]},
            ],
        )

        sold_out = self.client.get(f"/api/farmer/products/{self.prod2.id}/").data["data"]
        self.assertEqual(sold_out["availability"], "OUT_OF_STOCK")

    def test_patch_only_writes_changed_fields(self):
        self.client.force_authenticate(user=self.farmer_user)
        with mock.patch.object(Product, "save", autospec=True, side_effect=Product.save) as save:
            res = self.client.patch(f"/api/farmer/products/{self.prod1.id}/", {"name": "Heirloom Tomato"}, format="json")
        self.assertEqual(res.status_code, 200)
        update_fields = save.call_args_list[0].kwargs["update_fields"]
        self.assertIn("name", update_fields)
        self.assertNotIn("stock_quantity", update_fields)
        for call in save.call_args_list:
            self.assertNotIn("stock_quantity", call.kwargs["update_fields"])

    def test_restock_notification_failure_is_logged_not_raised(self):
        FavoriteProduct.objects.create(customer=self.customer_user, product=self.prod2)
        self.client.force_authenticate(user=self.farmer_user)
        with mock.patch("catalog.services.farmer_product.notify", side_effect=RuntimeError("smtp down")), \
                self.assertLogs("marketlink", level="ERROR"):
            res = self.client.patch(f"/api/farmer/products/{self.prod2.id}/", {"stock_quantity": 5}, format="json")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["restock_notified"], 0)
        self.prod2.refresh_from_db()
        self.assertEqual(self.prod2.stock_quantity, 5)


    def _order_for_prod1(self, *, qty: int, start_offset: timedelta, end_offset: timedelta, status: str) -> Order:
        now = timezone.now()
        market = Market.objects.create(
            name=f"Market {Market.objects.count() + 1}",
            address="Road 1",
            latitude=Decimal("10.0"),
            longitude=Decimal("106.0"),
            open_time=time(6, 0),
            close_time=time(18, 0),
            is_active=True,
        )
        fm = FarmerMarket.objects.create(farmer=self.farmer_profile, market=market, stall_label="S1")
        slot = PickupSlot.objects.create(
            farmer_market=fm, day_of_week=1, start_time=time(7, 0), end_time=time(9, 0), is_active=True
        )
        start = now + start_offset
        order = Order.objects.create(
            customer=self.customer_user,
            farmer=self.farmer_profile,
            market=market,
            pickup_slot=slot,
            pickup_date=start.date(),
            pickup_start_at=start,
            pickup_end_at=now + end_offset,
            cutoff_at=start - timedelta(hours=12),
            status=status,
            total_amount=Decimal("3.50") * qty,
        )
        OrderItem.objects.create(
            order=order,
            product=self.prod1,
            product_name=self.prod1.name,
            unit=Unit.KG,
            unit_price=Decimal("3.50"),
            quantity=qty,
            line_total=Decimal("3.50") * qty,
        )
        return order

    def test_fa18_during_market_keeps_goods_of_orders_being_picked_up(self):
        self._order_for_prod1(
            qty=5, start_offset=-timedelta(minutes=30), end_offset=timedelta(minutes=90),
            status=OrderStatus.ACCEPTED,
        )
        self.client.force_authenticate(user=self.farmer_user)
        preview = self.client.get("/api/farmer/products/weekly-template-preview/").data["data"]
        tomato = next(r for r in preview["rows"] if r["product_id"] == self.prod1.id)
        self.assertEqual(tomato["held_quantity"], 5)
        self.assertEqual(tomato["new_stock"], 20)

        res = self.client.post("/api/farmer/products/apply-weekly-template/", {})
        self.assertEqual(res.status_code, 200)
        self.prod1.refresh_from_db()
        self.assertEqual(self.prod1.stock_quantity, 20)

    def test_fa17_overdue_orders_are_order_summaries(self):
        overdue = self._order_for_prod1(
            qty=2, start_offset=-timedelta(days=1), end_offset=-timedelta(days=1) + timedelta(hours=2),
            status=OrderStatus.READY_FOR_PICKUP,
        )
        self.client.force_authenticate(user=self.farmer_user)
        preview = self.client.get("/api/farmer/products/weekly-template-preview/").data["data"]
        self.assertEqual(len(preview["overdue_orders"]), 1)
        row = preview["overdue_orders"][0]
        self.assertEqual(row["id"], overdue.id)
        self.assertEqual(row["version"], overdue.version)
        self.assertEqual(row["customer"]["full_name"], "Alice Customer")
        self.assertEqual(row["total_amount"], "7.00")
        tomato = next(r for r in preview["rows"] if r["product_id"] == self.prod1.id)
        self.assertEqual(tomato["held_quantity"], 0)

    def test_fa18_suspended_farmer_gets_farmer_suspended(self):
        self.farmer_profile.status = FarmerStatus.SUSPENDED
        self.farmer_profile.save(update_fields=["status"])
        self.client.force_authenticate(user=self.farmer_user)
        res = self.client.post("/api/farmer/products/apply-weekly-template/", {})
        self.assertEqual(res.status_code, 403)
        self.assertEqual(res.data["code"], ErrorCode.FARMER_SUSPENDED)

    def test_fa17_rows_carry_category_and_markets_for_filtering(self):
        ProductMarket.objects.filter(product=self.prod2).delete()
        self.client.force_authenticate(user=self.farmer_user)
        rows = self.client.get("/api/farmer/products/weekly-template-preview/").data["data"]["rows"]
        by_id = {row["product_id"]: row for row in rows}

        self.assertEqual(by_id[self.prod1.id]["category"], {"id": self.category.id, "name": "Vegetables"})
        self.assertEqual(by_id[self.prod1.id]["market_ids"], [self.home_market.id])
        self.assertEqual(by_id[self.prod2.id]["market_ids"], [])

    def test_fa18_apply_one_product_leaves_the_others_alone(self):
        self.client.force_authenticate(user=self.farmer_user)
        res = self.client.post(
            "/api/farmer/products/apply-weekly-template/", {"product_ids": [self.prod2.id]}, format="json"
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["updated_count"], 1)
        self.prod1.refresh_from_db()
        self.prod2.refresh_from_db()
        self.assertEqual(self.prod2.stock_quantity, 15)
        self.assertEqual(self.prod1.stock_quantity, 20)

    def test_fa18_apply_skips_another_farmers_product(self):
        other_product = Product.objects.create(
            review_status=ReviewStatus.APPROVED,
            farmer=self.pending_farmer_profile,
            category=self.category,
            name="Other Farm Beans",
            price=Decimal("1.00"),
            unit=Unit.KG,
            stock_quantity=3,
            weekly_default_quantity=40,
        )
        self.client.force_authenticate(user=self.farmer_user)
        res = self.client.post(
            "/api/farmer/products/apply-weekly-template/", {"product_ids": [other_product.id]}, format="json"
        )

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["updated_count"], 0)
        other_product.refresh_from_db()
        self.assertEqual(other_product.stock_quantity, 3)


    def test_renaming_an_approved_listing_sends_it_back_for_review_and_off_the_shelf(self):
        self.client.force_authenticate(user=self.farmer_user)
        res = self.client.patch(f"/api/farmer/products/{self.prod1.id}/", {"name": "Honda Wave"}, format="json")

        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["data"]["sent_for_review"])
        self.assertEqual(res.data["data"]["review_status"], ReviewStatus.PENDING)
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(f"/api/public/products/{self.prod1.id}/").status_code, 404)

    def test_price_stock_cap_or_a_resent_name_keep_the_listing_approved(self):
        self.client.force_authenticate(user=self.farmer_user)
        res = self.client.patch(
            f"/api/farmer/products/{self.prod1.id}/",
            {"name": self.prod1.name, "price": "4.20", "stock_quantity": 7, "max_per_order": 3},
            format="json",
        )

        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data["data"]["sent_for_review"])
        self.prod1.refresh_from_db()
        self.assertEqual(self.prod1.review_status, ReviewStatus.APPROVED)

    def test_editing_a_rejected_listing_resubmits_it(self):
        self.prod1.review_status = ReviewStatus.REJECTED
        self.prod1.review_note = "Photo is not the product"
        self.prod1.save(update_fields=["review_status", "review_note"])
        self.client.force_authenticate(user=self.farmer_user)

        res = self.client.patch(f"/api/farmer/products/{self.prod1.id}/", {"description": "Fresh from the farm"}, format="json")

        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["review_status"], ReviewStatus.PENDING)
        self.assertIsNone(res.data["data"]["review_note"])

    def test_orders_already_placed_keep_moving_while_the_listing_is_in_review(self):
        order = self._order_for_prod1(
            qty=2, start_offset=-timedelta(minutes=30), end_offset=timedelta(minutes=90),
            status=OrderStatus.ACCEPTED,
        )
        self.client.force_authenticate(user=self.farmer_user)
        self.client.patch(f"/api/farmer/products/{self.prod1.id}/", {"name": "Renamed tomato"}, format="json")
        self.prod1.refresh_from_db()
        self.assertEqual(self.prod1.review_status, ReviewStatus.PENDING)

        ready = self.client.post(f"/api/farmer/orders/{order.id}/ready/", {}, format="json", HTTP_IF_MATCH=str(order.version))
        self.assertEqual(ready.status_code, 200, ready.data)
        done = self.client.post(
            f"/api/farmer/orders/{order.id}/complete/", {}, format="json", HTTP_IF_MATCH=str(ready.data["data"]["version"])
        )
        self.assertEqual(done.status_code, 200, done.data)
        self.assertEqual(done.data["data"]["status"], OrderStatus.COMPLETED)

    def test_max_per_order_is_saved_validated_and_clearable(self):
        self.client.force_authenticate(user=self.farmer_user)
        url = f"/api/farmer/products/{self.prod1.id}/"

        self.assertEqual(self.client.patch(url, {"max_per_order": 0}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"max_per_order": 1000}, format="json").status_code, 400)
        self.assertEqual(self.client.patch(url, {"max_per_order": 10}, format="json").data["data"]["max_per_order"], 10)
        self.assertIsNone(self.client.patch(url, {"max_per_order": None}, format="json").data["data"]["max_per_order"])

    def test_state_filters_for_listings_in_review_and_rejected(self):
        self.prod1.review_status = ReviewStatus.PENDING
        self.prod1.save(update_fields=["review_status"])
        self.prod2.review_status = ReviewStatus.REJECTED
        self.prod2.save(update_fields=["review_status"])
        self.client.force_authenticate(user=self.farmer_user)

        def ids(state):
            return [row["id"] for row in self.client.get(f"/api/farmer/products/?state={state}").data["data"]["results"]]

        self.assertEqual(ids("in_review"), [self.prod1.id])
        self.assertEqual(ids("rejected"), [self.prod2.id])
        self.assertNotIn(self.prod1.id, ids("in_stock"))

    def test_min_per_order_defaults_to_one_and_cannot_exceed_the_max(self):
        self.client.force_authenticate(user=self.farmer_user)
        url = f"/api/farmer/products/{self.prod1.id}/"
        self.assertEqual(self.client.get(url).data["data"]["min_per_order"], 1)

        created = self.client.post(
            "/api/farmer/products/",
            {"name": "Bulk rice", "category_id": self.category.id, "price": "2.00", "unit": "KG",
             "stock_quantity": 50, "min_per_order": 5, "max_per_order": 3},
            format="json",
        )
        self.assertEqual(created.status_code, 400)
        self.assertIn("min_per_order", created.data["errors"])

        self.assertEqual(self.client.patch(url, {"max_per_order": 4}, format="json").status_code, 200)
        too_high = self.client.patch(url, {"min_per_order": 5}, format="json")
        self.assertEqual(too_high.status_code, 400)
        self.assertIn("min_per_order", too_high.data["errors"])
        self.assertEqual(self.client.patch(url, {"min_per_order": 2}, format="json").data["data"]["min_per_order"], 2)
