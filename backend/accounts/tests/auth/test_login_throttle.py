"""S1 / S1+: the sign-in limits cannot be dodged by faking an IP or by switching IPs."""

from unittest import mock

import pytest
from django.test import RequestFactory
from rest_framework.settings import api_settings

from accounts.tests.auth.conftest import PASSWORD
from marketlink_core.http import client_ip

URL = "/api/auth/login/"
ADMIN_URL = "/api/auth/admin/login/"
WRONG = "Wrong2026x"


def _login(api, email, password=PASSWORD, url=URL, **extra):
    return api.post(url, {"email": email, "password": password}, format="json", **extra)


def _rates(**overrides):
    rates = dict(api_settings.DEFAULT_THROTTLE_RATES, **overrides)
    return mock.patch("rest_framework.throttling.SimpleRateThrottle.THROTTLE_RATES", rates)


@pytest.mark.django_db
class TestForwardedForCannotResetTheIpLimit:
    def test_the_configured_settings_never_trust_the_raw_header(self, api, customer):
        # No mock: with NUM_PROXIES unset (None) DRF keyed anonymous throttles on the raw
        # X-Forwarded-For header, so a new fake IP per request reset the limit.
        assert api_settings.NUM_PROXIES is not None
        for attempt in range(5):
            _login(api, "alice@example.com", WRONG, HTTP_X_FORWARDED_FOR=f"198.51.100.{attempt}")

        response = _login(api, "alice@example.com", HTTP_X_FORWARDED_FOR="198.51.100.99")

        assert response.status_code == 429

    def test_without_a_proxy_a_forged_header_is_ignored(self, api, customer):
        with mock.patch.object(api_settings, "NUM_PROXIES", 0):
            for attempt in range(5):
                _login(api, "alice@example.com", WRONG, HTTP_X_FORWARDED_FOR=f"198.51.100.{attempt}")

            response = _login(api, "alice@example.com", HTTP_X_FORWARDED_FOR="198.51.100.99")

        assert (response.status_code, response.json()["code"]) == (429, "THROTTLED")

    def test_behind_one_proxy_only_the_proxy_entry_counts(self, api, customer):
        # The client controls everything before the last entry; the proxy appends the real IP.
        with mock.patch.object(api_settings, "NUM_PROXIES", 1):
            for attempt in range(5):
                _login(
                    api, "alice@example.com", WRONG,
                    HTTP_X_FORWARDED_FOR=f"198.51.100.{attempt}, 203.0.113.7",
                )

            response = _login(
                api, "alice@example.com", HTTP_X_FORWARDED_FOR="198.51.100.99, 203.0.113.7"
            )

        assert response.status_code == 429

    def test_behind_one_proxy_different_clients_keep_separate_limits(self, api, customer):
        with mock.patch.object(api_settings, "NUM_PROXIES", 1):
            for _ in range(5):
                _login(api, "alice@example.com", WRONG, HTTP_X_FORWARDED_FOR="203.0.113.7")

            response = _login(api, "alice@example.com", HTTP_X_FORWARDED_FOR="203.0.113.8")

        assert response.status_code == 200


class TestClientIp:
    factory = RequestFactory()

    def test_without_a_proxy_uses_remote_addr(self):
        request = self.factory.get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="1.2.3.4")

        with mock.patch.object(api_settings, "NUM_PROXIES", 0):
            assert client_ip(request) == "10.0.0.1"

    def test_behind_one_proxy_uses_the_entry_it_appended(self):
        request = self.factory.get(
            "/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="1.2.3.4, 203.0.113.7"
        )

        with mock.patch.object(api_settings, "NUM_PROXIES", 1):
            assert client_ip(request) == "203.0.113.7"

    def test_garbage_is_not_stored_as_an_ip(self):
        request = self.factory.get("/", REMOTE_ADDR="10.0.0.1", HTTP_X_FORWARDED_FOR="not-an-ip")

        with mock.patch.object(api_settings, "NUM_PROXIES", 1):
            assert client_ip(request) is None


@pytest.mark.django_db
class TestFailedSignInsPerEmail:
    def test_failures_from_many_ips_lock_the_email(self, api, customer):
        with _rates(login="100/min", login_email="3/hour"):
            for attempt in range(3):
                _login(api, "alice@example.com", WRONG, REMOTE_ADDR=f"198.51.100.{attempt}")

            response = _login(api, "alice@example.com", REMOTE_ADDR="198.51.100.50")

        assert (response.status_code, response.json()["code"]) == (429, "THROTTLED")

    def test_successful_sign_ins_are_not_counted(self, api, customer):
        with _rates(login="100/min", login_email="3/hour"):
            for _ in range(5):
                assert _login(api, "alice@example.com").status_code == 200

    def test_email_case_and_spaces_share_one_counter(self, api, customer):
        with _rates(login="100/min", login_email="2/hour"):
            _login(api, "ALICE@example.com", WRONG)
            _login(api, "  alice@EXAMPLE.com ", WRONG)

            response = _login(api, "alice@example.com")

        assert response.status_code == 429

    def test_another_email_is_not_affected(self, api, customer, farmer):
        with _rates(login="100/min", login_email="2/hour"):
            for _ in range(2):
                _login(api, "alice@example.com", WRONG)

            response = _login(api, "farmer@example.com")

        assert response.status_code == 200

    def test_admin_portal_is_limited_too(self, api, admin_user):
        with _rates(admin_login="100/min", login_email="2/hour"):
            for attempt in range(2):
                _login(api, "admin@example.com", WRONG, url=ADMIN_URL, REMOTE_ADDR=f"198.51.100.{attempt}")

            response = _login(api, "admin@example.com", url=ADMIN_URL, REMOTE_ADDR="198.51.100.50")

        assert response.status_code == 429

    def test_locked_account_with_right_password_is_not_counted(self, api, customer):
        customer.is_active = False
        customer.save()

        with _rates(login="100/min", login_email="2/hour"):
            for _ in range(3):
                response = _login(api, "alice@example.com")

        assert response.json()["code"] == "ACCOUNT_LOCKED"
