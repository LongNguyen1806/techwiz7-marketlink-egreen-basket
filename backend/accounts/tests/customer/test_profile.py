import io
from unittest import mock

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from PIL import Image

from accounts.auth.tokens import issue_tokens
from accounts.services.customer_registration_service import register_customer
from accounts.tests.auth.conftest import PASSWORD, bearer

URL = "/api/customer/profile/"
PHONE_TAKEN = ["This phone number is already registered."]


def _auth(user) -> dict:
    return bearer(issue_tokens(user)["access"])


def _patch(api, user, body):
    return api.patch(URL, body, format="json", **_auth(user))


@pytest.fixture
def other_customer(db):
    return register_customer(
        email="carol@example.com", password=PASSWORD, full_name="Carol Le",
        phone="0901112233", address="9 River Road, District 3",
    )


@pytest.mark.django_db
class TestGetProfile:
    def test_returns_own_profile(self, api, customer):
        response = api.get(URL, **_auth(customer))

        assert response.status_code == 200
        assert response.json()["data"] == {
            "full_name": "Alice Nguyen",
            "phone": "0912345678",
            "address": "12 Market Street, District 1",
            "email": "alice@example.com",
            "image": None,
        }

    def test_requires_login(self, api):
        assert api.get(URL).status_code == 401

    @pytest.mark.parametrize("account", ["farmer", "admin_user"])
    def test_other_roles_are_forbidden(self, api, request, account):
        user = request.getfixturevalue(account)

        assert api.get(URL, **_auth(user)).status_code == 403


@pytest.mark.django_db
class TestUpdateProfile:
    def test_updates_only_the_fields_sent(self, api, customer):
        response = _patch(api, customer, {"full_name": "Alice Tran"})

        assert response.status_code == 200
        data = response.json()["data"]
        assert (data["full_name"], data["phone"], data["address"]) == (
            "Alice Tran", "0912345678", "12 Market Street, District 1"
        )
        customer.customer_profile.refresh_from_db()
        assert customer.customer_profile.full_name == "Alice Tran"

    def test_phone_is_normalised(self, api, customer):
        response = _patch(api, customer, {"phone": "+84 98 765 4321"})

        assert response.status_code == 200
        assert response.json()["data"]["phone"] == "0987654321"

    def test_phone_of_another_customer_is_rejected(self, api, customer, other_customer):
        response = _patch(api, customer, {"phone": "090.111.2233"})

        assert (response.status_code, response.json()["code"]) == (400, "VALIDATION_ERROR")
        assert response.json()["errors"]["phone"] == PHONE_TAKEN
        customer.customer_profile.refresh_from_db()
        assert customer.customer_profile.phone == "0912345678"

    def test_phone_taken_by_a_concurrent_request_is_still_a_field_error(self, api, customer, other_customer):
        with mock.patch("accounts.services.customer_profile_service.phone_taken", side_effect=[False, True]):
            response = _patch(api, customer, {"phone": "0901112233"})

        assert (response.status_code, response.json()["errors"]["phone"]) == (400, PHONE_TAKEN)

    def test_keeping_your_own_phone_is_fine(self, api, customer):
        response = _patch(api, customer, {"phone": "+84912345678", "address": "34 New Street, District 5"})

        assert response.status_code == 200
        assert response.json()["data"]["address"] == "34 New Street, District 5"

    @pytest.mark.parametrize("body, field", [
        ({"full_name": "A"}, "full_name"),
        ({"phone": "12345"}, "phone"),
        ({"address": "abc"}, "address"),
        ({"full_name": ""}, "full_name"),
    ])
    def test_invalid_values_are_rejected(self, api, customer, body, field):
        response = _patch(api, customer, body)

        assert (response.status_code, response.json()["code"]) == (400, "VALIDATION_ERROR")
        assert field in response.json()["errors"]

    def test_email_cannot_be_changed(self, api, customer):
        response = _patch(api, customer, {"email": "mallory@example.com"})

        assert response.status_code == 200
        assert response.json()["data"]["email"] == "alice@example.com"
        customer.refresh_from_db()
        assert customer.email == "alice@example.com"

    def test_new_name_shows_up_in_me(self, api, customer):
        _patch(api, customer, {"full_name": "Alice Tran"})

        assert api.get("/api/auth/me/", **_auth(customer)).json()["data"]["display_name"] == "Alice Tran"

    def test_other_roles_are_forbidden(self, api, farmer):
        assert _patch(api, farmer, {"full_name": "Bob"}).status_code == 403


def _photo(name="me.png", fmt="PNG", content_type="image/png"):
    buffer = io.BytesIO()
    Image.new("RGB", (8, 8), "green").save(buffer, fmt)
    return SimpleUploadedFile(name, buffer.getvalue(), content_type=content_type)


def _upload(api, user, file):
    return api.patch(URL, {"image": file}, format="multipart", **_auth(user))


@pytest.mark.django_db
class TestProfilePhoto:
    def test_upload_shows_in_profile_and_account_menu(self, api, customer):
        response = _upload(api, customer, _photo())

        assert response.status_code == 200
        url = response.json()["data"]["image"]
        assert "/media/customers/" in url
        assert api.get("/api/auth/me/", **_auth(customer)).json()["data"]["avatar"] == url
        customer.customer_profile.refresh_from_db()
        customer.customer_profile.image.delete(save=False)

    def test_replacing_or_removing_deletes_the_old_file(self, api, customer, django_capture_on_commit_callbacks):
        _upload(api, customer, _photo())
        profile = customer.customer_profile
        profile.refresh_from_db()
        first = profile.image.name
        storage = profile.image.storage

        with django_capture_on_commit_callbacks(execute=True):
            _upload(api, customer, _photo("new.png"))
        profile.refresh_from_db()
        second = profile.image.name
        assert second != first
        assert not storage.exists(first)

        with django_capture_on_commit_callbacks(execute=True):
            response = _patch(api, customer, {"image": None})
        assert response.status_code == 200
        assert response.json()["data"]["image"] is None
        profile.refresh_from_db()
        assert not profile.image
        assert not storage.exists(second)

    def test_a_file_that_is_not_an_image_is_rejected(self, api, customer):
        fake = SimpleUploadedFile("me.png", b"<html>not an image</html>", content_type="image/png")

        response = _upload(api, customer, fake)

        assert response.status_code == 400
        assert "image" in response.json()["errors"]
        customer.customer_profile.refresh_from_db()
        assert not customer.customer_profile.image
