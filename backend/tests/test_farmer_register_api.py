from decimal import Decimal
from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from accounts.models import CustomUser, FarmerProfile, FarmerStatus, Role, RoleCode
from marketlink_core.exceptions import ErrorCode

URL = "/api/auth/register/farmer/"
GEOCODE = "accounts.services.registration.geocode_address"


@override_settings(GEOCODING_ENABLED=False)
class FarmerRegisterAPITestCase(TestCase):
    """F1: AU-02 (FR-02, G-11, D-028, D-031, D-032)."""

    def setUp(self):
        cache.clear()
        self.client = APIClient()
        self.payload = {
            "email": "  New.Farmer@Example.com ",
            "password": "garden2026",
            "confirm_password": "garden2026",
            "stall_name": "Fresh Garden",
            "contact_person": "Nguyen Van Moi",
            "phone": "+84 912 000 111",
            "address": "12 Le Loi, District 1, Ho Chi Minh City",
            "operating_days": [6, 2, 4],
        }

    def _register(self, **overrides):
        body = {**self.payload, **overrides}
        return self.client.post(URL, body, format="json")

    def test_register_success(self):
        with mock.patch(GEOCODE, return_value=(Decimal("10.772000"), Decimal("106.698000"))) as geocode:
            res = self._register()
        self.assertEqual(res.status_code, 201, res.data)
        data = res.data["data"]
        self.assertTrue(data["access"])
        self.assertTrue(data["refresh"])
        user = CustomUser.objects.get(email="new.farmer@example.com")
        self.assertEqual(
            data["user"],
            {
                "id": user.pk,
                "email": "new.farmer@example.com",
                "role": RoleCode.FARMER,
                "display_name": "Fresh Garden",
                "farmer_status": FarmerStatus.PENDING,
            },
        )
        self.assertTrue(user.check_password("garden2026"))
        self.assertEqual(user.role.code, RoleCode.FARMER)
        profile = FarmerProfile.objects.get(user=user)
        self.assertEqual(profile.status, FarmerStatus.PENDING)
        self.assertEqual(profile.phone, "0912000111")
        self.assertEqual(profile.operating_days, [2, 4, 6])
        geocode.assert_called_once_with("12 Le Loi, District 1, Ho Chi Minh City")
        self.assertEqual(profile.latitude, Decimal("10.772000"))
        self.assertNotIn("password", data)

    def test_a_pin_from_the_map_is_kept_and_the_address_not_looked_up(self):
        with mock.patch(GEOCODE) as geocode:
            res = self._register(latitude=10.8597391234, longitude=106.6006592)
        self.assertEqual(res.status_code, 201, res.data)
        profile = FarmerProfile.objects.get(user__email="new.farmer@example.com")
        self.assertEqual(profile.latitude, Decimal("10.859739"))
        self.assertEqual(profile.longitude, Decimal("106.600659"))
        geocode.assert_not_called()

    def test_half_a_pin_is_refused(self):
        with mock.patch(GEOCODE) as geocode:
            res = self._register(latitude=10.85)
        self.assertEqual(res.status_code, 400)
        self.assertIn("longitude", res.data["errors"])
        self.assertFalse(CustomUser.objects.filter(email="new.farmer@example.com").exists())
        geocode.assert_not_called()

    def test_access_token_opens_farmer_profile(self):
        with mock.patch(GEOCODE, return_value=None):
            access = self._register().data["data"]["access"]
        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        res = client.get("/api/farmer/profile/")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.data["data"]["status"], FarmerStatus.PENDING)
        self.assertFalse(res.data["data"]["location_found"])

    def _assert_registered_without_coordinates(self, email):
        profile = FarmerProfile.objects.get(user__email=email)
        self.assertIsNone(profile.latitude)
        self.assertIsNone(profile.longitude)

    def test_address_not_found_does_not_block_registration(self):
        with mock.patch(GEOCODE, return_value=None):
            res = self._register(email="notfound@example.com", phone="0912000222")
        self.assertEqual(res.status_code, 201)
        self._assert_registered_without_coordinates("notfound@example.com")

    def test_geocoding_crash_does_not_block_registration(self):
        with mock.patch(GEOCODE, side_effect=RuntimeError("boom")), self.assertLogs("marketlink", "ERROR") as logs:
            res = self._register(email="crash@example.com", phone="0912000333")
        self.assertEqual(res.status_code, 201)
        self.assertIn("Geocoding after farmer registration failed", logs.output[0])
        self._assert_registered_without_coordinates("crash@example.com")

    def test_email_exists(self):
        role = Role.objects.get(code=RoleCode.CUSTOMER)
        CustomUser.objects.create_user(email="new.farmer@example.com", password="x1234567", role=role, is_active=False)
        with mock.patch(GEOCODE) as geocode:
            res = self._register()
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["code"], ErrorCode.EMAIL_EXISTS)
        self.assertIn("email", res.data["errors"])
        geocode.assert_not_called()
        self.assertFalse(FarmerProfile.objects.filter(stall_name="Fresh Garden").exists())

    def test_phone_taken_by_another_farmer(self):
        with mock.patch(GEOCODE, return_value=None):
            self.assertEqual(self._register().status_code, 201)
            res = self._register(email="second@example.com", phone="0912.000.111")
        self.assertEqual(res.status_code, 400)
        self.assertEqual(res.data["code"], ErrorCode.VALIDATION_ERROR)
        self.assertIn("phone", res.data["errors"])

    def test_password_rules(self):
        cases = [
            ({"password": "abc123", "confirm_password": "abc123"}, "password"),
            ({"password": "onlyletters", "confirm_password": "onlyletters"}, "password"),
            ({"password": "12345678", "confirm_password": "12345678"}, "password"),
            ({"confirm_password": "garden2027"}, "confirm_password"),
        ]
        for overrides, field in cases:
            with self.subTest(overrides=overrides):
                res = self._register(**overrides)
                self.assertEqual(res.status_code, 400)
                self.assertIn(field, res.data["errors"])
        self.assertFalse(CustomUser.objects.filter(email="new.farmer@example.com").exists())

    def test_field_rules(self):
        cases = [
            ({"email": "not-an-email"}, "email"),
            ({"phone": "0123456789"}, "phone"),
            ({"stall_name": "A"}, "stall_name"),
            ({"contact_person": "B"}, "contact_person"),
            ({"address": "abc"}, "address"),
            ({"operating_days": []}, "operating_days"),
            ({"operating_days": [0, 8]}, "operating_days"),
        ]
        for overrides, field in cases:
            with self.subTest(overrides=overrides):
                res = self._register(**overrides)
                self.assertEqual(res.status_code, 400)
                self.assertTrue(any(key.startswith(field) for key in res.data["errors"]), res.data["errors"])

    def test_missing_fields_are_all_reported(self):
        res = self.client.post(URL, {}, format="json")
        self.assertEqual(res.status_code, 400)
        for field in ("email", "password", "confirm_password", "stall_name", "contact_person", "phone", "address", "operating_days"):
            self.assertIn(field, res.data["errors"])

    def test_register_is_throttled(self):
        with mock.patch(GEOCODE, return_value=None), mock.patch(
            "rest_framework.throttling.ScopedRateThrottle.THROTTLE_RATES", {"register": "2/hour"}
        ):
            codes = [self.client.post(URL, {}, format="json").status_code for _ in range(3)]
        self.assertEqual(codes, [400, 400, 429])
