from unittest import mock

import pytest

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
