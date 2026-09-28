import uuid

import pytest

from accounts.tests.auth.conftest import PASSWORD
from system.models import AuditLog

URL = "/api/auth/login/"


def _login(api, email, password=PASSWORD, **headers):
    return api.post(URL, {"email": email, "password": password}, format="json", **headers)


@pytest.mark.django_db
class TestLogin:
    def test_returns_tokens_and_me(self, api, customer):
        response = _login(api, "alice@example.com")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["access"] and data["refresh"]
        assert data["user"]["email"] == "alice@example.com"
        assert data["user"]["role"] == "CUSTOMER"

    def test_email_is_case_insensitive(self, api, customer):
        response = _login(api, "  ALICE@Example.com ")

        assert response.status_code == 200

    def test_farmer_me_uses_stall_name_and_status(self, api, farmer):
        user = _login(api, "farmer@example.com").json()["data"]["user"]

        assert user["display_name"] == "Green Stall"
        assert user["farmer_status"] == "PENDING"

    def test_admin_is_rejected_even_with_the_right_password(self, api, admin_user):
        response = _login(api, "admin@example.com")

        assert (response.status_code, response.json()["code"]) == (401, "INVALID_CREDENTIALS")

    def test_wrong_password_and_unknown_email_look_identical(self, api, customer):
        wrong_password = _login(api, "alice@example.com", "Wrong2026x")
        unknown_email = _login(api, "nobody@example.com")

        for response in (wrong_password, unknown_email):
            assert response.status_code == 401
            assert response.json()["code"] == "INVALID_CREDENTIALS"
        assert wrong_password.json()["message"] == unknown_email.json()["message"]

    def test_locked_account_with_correct_password_returns_reason(self, api, customer):
        customer.is_active = False
        customer.save()
        customer.customer_profile.deactivation_reason = "Repeated no-shows"
        customer.customer_profile.save()

        response = _login(api, "alice@example.com")

        assert response.status_code == 403
        assert response.json()["code"] == "ACCOUNT_LOCKED"
        assert response.json()["errors"] == {"reason": ["Repeated no-shows"]}

    def test_locked_account_with_wrong_password_does_not_reveal_lock(self, api, customer):
        customer.is_active = False
        customer.save()

        response = _login(api, "alice@example.com", "Wrong2026x")

        assert response.status_code == 401
        assert response.json()["code"] == "INVALID_CREDENTIALS"

    def test_sixth_attempt_in_a_minute_is_throttled(self, api, customer):
        for _ in range(5):
            _login(api, "alice@example.com", "Wrong2026x")

        response = _login(api, "alice@example.com")

        assert response.status_code == 429
        assert response.json()["code"] == "THROTTLED"


@pytest.mark.django_db
class TestLoginAudit:
    def test_success_writes_login_row(self, api, customer):
        request_id = str(uuid.uuid4())

        _login(api, "alice@example.com", HTTP_X_REQUEST_ID=request_id, HTTP_USER_AGENT="pytest")

        log = AuditLog.objects.get(action="LOGIN")
        assert log.user_id == customer.id
        assert (log.status_code, log.request_id) == (200, request_id)
        assert (log.endpoint, log.method) == (URL, "POST")
        assert log.ip_address == "127.0.0.1"
        assert log.user_agent == "pytest"

    def test_failure_writes_login_failed_row_without_password(self, api, customer):
        _login(api, "alice@example.com", "Wrong2026x")

        log = AuditLog.objects.get(action="LOGIN_FAILED")
        assert log.user_id is None
        assert log.status_code == 401
        assert log.details == {"email": "alice@example.com", "error": "INVALID_CREDENTIALS"}
        assert "Wrong2026x" not in str(log.details)

    def test_locked_login_is_audited_as_failure(self, api, customer):
        customer.is_active = False
        customer.save()

        _login(api, "alice@example.com")

        log = AuditLog.objects.get(action="LOGIN_FAILED")
        assert (log.status_code, log.details["error"]) == (403, "ACCOUNT_LOCKED")
