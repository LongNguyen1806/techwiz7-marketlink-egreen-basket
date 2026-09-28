import pytest

from accounts.auth.tokens import issue_tokens
from accounts.tests.auth.conftest import bearer

URL = "/api/auth/me/"


@pytest.mark.django_db
class TestMe:
    def test_returns_current_user(self, api, customer):
        access = issue_tokens(customer)["access"]

        response = api.get(URL, **bearer(access))

        assert response.status_code == 200
        assert response.json()["data"] == {
            "id": customer.id,
            "email": "alice@example.com",
            "role": "CUSTOMER",
            "display_name": "Alice Nguyen",
            "farmer_status": None,
            "avatar": None,
        }

    def test_requires_token(self, api):
        response = api.get(URL)

        assert response.status_code == 401
        assert response.json()["code"] == "NOT_AUTHENTICATED"

    def test_rejects_garbage_token(self, api):
        response = api.get(URL, **bearer("not.a.jwt"))

        assert response.status_code == 401
        assert response.json()["code"] == "NOT_AUTHENTICATED"

    def test_rejects_access_token_of_locked_user(self, api, customer):
        access = issue_tokens(customer)["access"]
        customer.is_active = False
        customer.save()

        response = api.get(URL, **bearer(access))

        assert response.status_code == 401
