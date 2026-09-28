import io
import json
import shutil
import tempfile
from datetime import datetime, time, timedelta
from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.utils import timezone
from PIL import Image
from rest_framework.test import APIClient

from accounts import geocoding
from accounts.models import CustomUser, CustomerProfile, FarmerProfile, FarmerStatus, Role, RoleCode
from catalog.models import Category, Product, Unit
from marketlink_core.exceptions import ErrorCode
from markets.models import FarmerClosure, FarmerMarket, Market, MarketOperatingDay, PickupSlot
from orders.models import Order, OrderStatus
from reviews.models import FarmerReview

URL = "/api/farmer/profile/"
GEOCODE = "accounts.services.farmer_profile.geocode_address"


def _jpeg_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (20, 20), (0, 128, 0)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _next_date_with_weekday(weekday: int, *, min_days_ahead: int = 1):
    day = timezone.localdate() + timedelta(days=min_days_ahead)
    while day.isoweekday() != weekday:
        day += timedelta(days=1)
    return day


@override_settings(GEOCODING_ENABLED=False)
class FarmerProfileAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        farmer_role, _ = Role.objects.get_or_create(code=RoleCode.FARMER, defaults={"name": "Farmer"})
        customer_role, _ = Role.objects.get_or_create(code=RoleCode.CUSTOMER, defaults={"name": "Customer"})

        self.farmer_user = CustomUser.objects.create(email="profile_farmer@marketlink.local", role=farmer_role)
        self.farmer = FarmerProfile.objects.create(
            user=self.farmer_user,
            stall_name="Green Leaf",
            contact_person="Tran Van Profile",
            phone="0988000111",
            address="12 Farm Road, District 1",
            status=FarmerStatus.APPROVED,
            operating_days=[2, 4, 6],
        )
        other_user = CustomUser.objects.create(email="other_farmer@marketlink.local", role=farmer_role)
        self.other_farmer = FarmerProfile.objects.create(
            user=other_user,
            stall_name="Other Stall",
            contact_person="Le Van Other",
            phone="0988000222",
            address="99 Other Road",
            operating_days=[1],
        )
        self.customer_user = CustomUser.objects.create(email="profile_customer@marketlink.local", role=customer_role)
        CustomerProfile.objects.create(
            user=self.customer_user, full_name="Nguyen Van Khach", phone="0911000111", address="1 Customer St"
        )

        self.market = Market.objects.create(
            name="Profile Market",
            address="1 Market Blvd",
            latitude=Decimal("10.776900"),
            longitude=Decimal("106.700900"),
            open_time="06:00:00",
            close_time="20:00:00",
        )
        for day in range(1, 8):
            MarketOperatingDay.objects.create(market=self.market, day_of_week=day)
        self.farmer_market = FarmerMarket.objects.create(farmer=self.farmer, market=self.market, stall_label="Row B")
        self.slot_tue = PickupSlot.objects.create(
            farmer_market=self.farmer_market, day_of_week=2, start_time="07:00", end_time="09:00"
        )
        self.slot_thu = PickupSlot.objects.create(
            farmer_market=self.farmer_market, day_of_week=4, start_time="07:00", end_time="09:00"
        )
        self.slot_sat_off = PickupSlot.objects.create(
            farmer_market=self.farmer_market, day_of_week=6, start_time="07:00", end_time="09:00", is_active=False
        )

        category = Category.objects.create(name="Vegetables")
        Product.objects.create(
            farmer=self.farmer, category=category, name="Cabbage", unit=Unit.KG, price=Decimal("2.00"), stock_quantity=5
        )
        Product.objects.create(
            farmer=self.farmer, category=category, name="Carrot", unit=Unit.KG, price=Decimal("1.00"), stock_quantity=0
        )
        self.client.force_authenticate(user=self.farmer_user)

    def _order(self, pickup_date, status=OrderStatus.PLACED) -> Order:
        tz = timezone.get_current_timezone()
        start_at = timezone.make_aware(datetime.combine(pickup_date, time(7, 0)), tz)
        return Order.objects.create(
            customer=self.customer_user,
            farmer=self.farmer,
            market=self.market,
            pickup_slot=self.slot_tue,
            stall_label="Row B",
            pickup_date=pickup_date,
            pickup_start_at=start_at,
            pickup_end_at=start_at + timedelta(hours=2),
            cutoff_at=start_at - timedelta(hours=12),
            total_amount=Decimal("2.00"),
            status=status,
        )

    def _patch(self, body, **kwargs):
        return self.client.patch(URL, body, format=kwargs.pop("format", "json"), **kwargs)


    def test_get_returns_farmer_public_and_owner_fields(self):
        res = self.client.get(URL)
        self.assertEqual(res.status_code, 200)
        data = res.data["data"]
        expected = {
            "id", "stall_name", "image", "rating_avg", "rating_count", "markets", "operating_days",
            "in_stock_product_count", "upcoming_closures", "distance_km", "is_favorite", "contact_person",
            "phone", "address", "description", "latitude", "longitude", "order_cutoff_hours",
            "pickup_windows", "email", "status", "status_reason", "location_found", "can_list_products",
        }
        self.assertEqual(set(data), expected)
        self.assertEqual(data["email"], "profile_farmer@marketlink.local")
        self.assertEqual(data["operating_days"], [2, 4, 6])
        self.assertEqual(data["in_stock_product_count"], 1)
        self.assertFalse(data["location_found"])
        self.assertIsNone(data["distance_km"])
        self.assertEqual(data["markets"], [{"market_id": self.market.pk, "market_name": "Profile Market", "stall_label": "Row B"}])
        slots = data["pickup_windows"][0]["slots"]
        self.assertEqual([slot["day_of_week"] for slot in slots], [2, 4, 6])
        self.assertEqual(slots[0]["start_time"], "07:00")
        self.assertFalse(slots[2]["is_active"])

    def test_get_rating_ignores_hidden_reviews_and_lists_upcoming_closures(self):
        visible_order = self._order(timezone.localdate() - timedelta(days=3), OrderStatus.COMPLETED)
        hidden_order = self._order(timezone.localdate() - timedelta(days=2), OrderStatus.COMPLETED)
        FarmerReview.objects.create(order=visible_order, rating=4)
        FarmerReview.objects.create(order=hidden_order, rating=1, is_hidden_by_admin=True)
        today = timezone.localdate()
        FarmerClosure.objects.create(farmer=self.farmer, start_date=today + timedelta(days=2), end_date=today + timedelta(days=3))
        FarmerClosure.objects.create(farmer=self.farmer, start_date=today - timedelta(days=9), end_date=today - timedelta(days=8))

        data = self.client.get(URL).data["data"]
        self.assertEqual(data["rating_avg"], 4.0)
        self.assertEqual(data["rating_count"], 1)
        self.assertEqual(len(data["upcoming_closures"]), 1)

    def test_requires_farmer_role(self):
        self.client.force_authenticate(user=None)
        self.assertEqual(self.client.get(URL).status_code, 401)
        self.client.force_authenticate(user=self.customer_user)
        self.assertEqual(self.client.get(URL).status_code, 403)


    def test_patch_simple_fields(self):
        res = self._patch(
            {"stall_name": "  Green Leaf 2 ", "contact_person": "Tran Van B", "description": "  ", "order_cutoff_hours": 24}
        )
        self.assertEqual(res.status_code, 200)
        self.farmer.refresh_from_db()
        self.assertEqual(self.farmer.stall_name, "Green Leaf 2")
        self.assertIsNone(self.farmer.description)
        self.assertEqual(self.farmer.order_cutoff_hours, 24)
        self.assertNotIn("deactivated_slot_count", res.data["data"])

    def test_email_and_status_are_not_writable(self):
        self._patch({"email": "hacker@x.com", "status": FarmerStatus.APPROVED, "stall_name": "Ok Name"})
        self.farmer.refresh_from_db()
        self.farmer_user.refresh_from_db()
        self.assertEqual(self.farmer_user.email, "profile_farmer@marketlink.local")
        self.assertEqual(self.farmer.stall_name, "Ok Name")

    def test_invalid_simple_fields(self):
        res = self._patch({"stall_name": "A", "order_cutoff_hours": 0, "address": "abc"})
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["code"], ErrorCode.VALIDATION_ERROR)
        for field in ("stall_name", "order_cutoff_hours", "address"):
            self.assertIn(field, res.data["errors"])

    def test_suspended_farmer_can_edit_profile(self):
        FarmerProfile.objects.filter(pk=self.farmer.pk).update(status=FarmerStatus.SUSPENDED)
        self.assertEqual(self._patch({"stall_name": "Still Mine"}).status_code, 200)


    def test_phone_is_normalized(self):
        self.assertEqual(self._patch({"phone": "+84 912.345.678"}).status_code, 200)
        self.farmer.refresh_from_db()
        self.assertEqual(self.farmer.phone, "0912345678")

    def test_phone_invalid_or_taken(self):
        res = self._patch({"phone": "0123"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("phone", res.data["errors"])
        res = self._patch({"phone": "098.800.0222"})
        self.assertEqual(res.status_code, 400)
        self.assertIn("phone", res.data["errors"])


    def test_coordinates_must_be_sent_together(self):
        res = self._patch({"latitude": 10.5})
        self.assertEqual(res.status_code, 400)
        self.assertIn("longitude", res.data["errors"])

    def test_dragged_pin_is_saved_without_geocoding(self):
        with mock.patch(GEOCODE) as geocode:
            res = self._patch({"address": "New address 123", "latitude": 10.12345678, "longitude": 106.1})
        self.assertEqual(res.status_code, 200)
        geocode.assert_not_called()
        self.assertTrue(res.data["data"]["location_found"])
        self.farmer.refresh_from_db()
        self.assertEqual(self.farmer.latitude, Decimal("10.123457"))

    def test_new_address_is_geocoded(self):
        with mock.patch(GEOCODE, return_value=(Decimal("10.800000"), Decimal("106.650000"))) as geocode:
            res = self._patch({"address": "45 Le Loi, District 1"})
        self.assertEqual(res.status_code, 200)
        geocode.assert_called_once_with("45 Le Loi, District 1")
        self.assertEqual(res.data["data"]["latitude"], 10.8)
        self.assertTrue(res.data["data"]["location_found"])

    def test_address_not_found_clears_coordinates(self):
        FarmerProfile.objects.filter(pk=self.farmer.pk).update(latitude=Decimal("10"), longitude=Decimal("106"))
        with mock.patch(GEOCODE, return_value=None):
            res = self._patch({"address": "Unknown place 999"})
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.data["data"]["location_found"])
        self.assertIsNone(res.data["data"]["latitude"])

    def test_same_address_is_not_geocoded_again(self):
        with mock.patch(GEOCODE) as geocode:
            self._patch({"address": "12 Farm Road, District 1"})
        geocode.assert_not_called()


    def test_operating_days_empty_or_invalid(self):
        for bad in ([], [0], [2, 2], ["x"]):
            with self.subTest(value=bad):
                res = self._patch({"operating_days": bad})
                self.assertEqual(res.status_code, 400)
                self.assertTrue(any(key.startswith("operating_days") for key in res.data["errors"]))

    def test_removing_day_with_open_order_is_blocked(self):
        order = self._order(_next_date_with_weekday(2))
        res = self._patch({"operating_days": [4, 6]})
        self.assertEqual(res.status_code, 422)
        self.assertEqual(res.data["code"], ErrorCode.RESOURCE_IN_USE)
        self.assertEqual(res.data["errors"]["order_ids"], [order.pk])
        self.farmer.refresh_from_db()
        self.slot_tue.refresh_from_db()
        self.assertEqual(self.farmer.operating_days, [2, 4, 6])
        self.assertTrue(self.slot_tue.is_active)

    def test_closed_or_past_orders_do_not_block(self):
        self._order(_next_date_with_weekday(2), OrderStatus.CANCELLED)
        past_tuesday = timezone.localdate() - timedelta(days=1)
        while past_tuesday.isoweekday() != 2:
            past_tuesday -= timedelta(days=1)
        self._order(past_tuesday, OrderStatus.ACCEPTED)
        self.assertEqual(self._patch({"operating_days": [4, 6]}).status_code, 200)

    def test_removing_day_switches_its_slots_off(self):
        res = self._patch({"operating_days": [6, 4]})
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["deactivated_slot_count"], 1)
        self.assertEqual(res.data["data"]["operating_days"], [4, 6])
        self.slot_tue.refresh_from_db()
        self.slot_thu.refresh_from_db()
        self.assertFalse(self.slot_tue.is_active)
        self.assertTrue(self.slot_thu.is_active)

    def test_adding_day_does_not_report_or_reactivate(self):
        res = self._patch({"operating_days": [2, 4, 6, 7]})
        self.assertEqual(res.status_code, 200)
        self.assertNotIn("deactivated_slot_count", res.data["data"])
        self.slot_sat_off.refresh_from_db()
        self.assertFalse(self.slot_sat_off.is_active)

    def test_operating_days_via_multipart(self):
        res = self.client.patch(URL, {"operating_days": ["2", "4"]}, format="multipart")
        self.assertEqual(res.status_code, 200, res.data)
        self.farmer.refresh_from_db()
        self.assertEqual(self.farmer.operating_days, [2, 4])


    def test_invalid_image_rejected(self):
        upload = SimpleUploadedFile("stall.jpg", b"not an image", content_type="image/jpeg")
        res = self.client.patch(URL, {"image": upload}, format="multipart")
        self.assertEqual(res.status_code, 400)
        self.assertIn("image", res.data["errors"])

    def test_image_replaced_and_old_file_removed(self):
        media_root = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, media_root, ignore_errors=True)
        with override_settings(MEDIA_ROOT=media_root):
            first = SimpleUploadedFile("a.jpg", _jpeg_bytes(), content_type="image/jpeg")
            with self.captureOnCommitCallbacks(execute=True):
                self.assertEqual(self.client.patch(URL, {"image": first}, format="multipart").status_code, 200)
            self.farmer.refresh_from_db()
            old_name = self.farmer.image.name
            storage = self.farmer.image.storage
            self.assertTrue(old_name.endswith(".jpg"))

            second = SimpleUploadedFile("b.jpg", _jpeg_bytes(), content_type="image/jpeg")
            with self.captureOnCommitCallbacks(execute=True):
                res = self.client.patch(URL, {"image": second}, format="multipart")
            self.assertEqual(res.status_code, 200)
            self.farmer.refresh_from_db()
            self.assertNotEqual(self.farmer.image.name, old_name)
            self.assertFalse(storage.exists(old_name))
            self.assertTrue(storage.exists(self.farmer.image.name))


class GeocodingTestCase(SimpleTestCase):
    def setUp(self):
        cache.clear()

    def _response(self, payload):
        response = mock.MagicMock()
        response.read.return_value = json.dumps(payload).encode("utf-8")
        response.__enter__.return_value = response
        return response

    @override_settings(GEOCODING_ENABLED=True)
    def test_parses_first_result(self):
        with mock.patch.object(geocoding, "urlopen", return_value=self._response([{"lat": "10.7769001234", "lon": "106.70098"}])) as opener:
            self.assertEqual(geocoding.geocode_address(" 1 Le Loi "), (Decimal("10.776900"), Decimal("106.700980")))
        request = opener.call_args.args[0]
        self.assertIn("countrycodes=vn", request.full_url)
        self.assertTrue(request.get_header("User-agent"))
        self.assertEqual(opener.call_args.kwargs["timeout"], 5)

    @override_settings(GEOCODING_ENABLED=True)
    def test_not_found_or_error_returns_none(self):
        with mock.patch.object(geocoding, "urlopen", return_value=self._response([])):
            self.assertIsNone(geocoding.geocode_address("nowhere"))
        cache.clear()
        with mock.patch.object(geocoding, "urlopen", side_effect=OSError("timeout")), self.assertLogs(
            "marketlink", "WARNING"
        ) as logs:
            self.assertIsNone(geocoding.geocode_address("somewhere"))
        self.assertIn("Geocoding request failed", logs.output[0])

    @override_settings(GEOCODING_ENABLED=False)
    def test_disabled_makes_no_request(self):
        with mock.patch.object(geocoding, "urlopen") as opener:
            self.assertIsNone(geocoding.geocode_address("1 Le Loi"))
        opener.assert_not_called()

    @override_settings(GEOCODING_ENABLED=True)
    def test_rate_limit_slot_is_shared(self):
        self.assertTrue(geocoding._acquire_rate_slot())
        with mock.patch.object(geocoding, "RATE_LIMIT_MAX_WAIT_SECONDS", 0):
            self.assertFalse(geocoding._acquire_rate_slot())
