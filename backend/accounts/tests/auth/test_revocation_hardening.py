from unittest import mock

import pytest
from django.core.cache.backends.base import InvalidCacheBackendError
from django.test import override_settings

from accounts.auth.tokens import issue_tokens
from accounts.checks import check_token_revocation_store
from accounts.tests.auth.conftest import PASSWORD, bearer

ME = "/api/auth/me/"
REFRESH = "/api/auth/refresh/"
LOGOUT = "/api/auth/logout/"
CHANGE_PASSWORD = "/api/auth/change-password/"


def _refresh(api, refresh):
    return api.post(REFRESH, {"refresh": refresh}, format="json")


@pytest.mark.django_db
class TestPasswordChangeExemptionIsScoped:
    def test_later_password_reset_elsewhere_also_kicks_the_device_that_changed_it(self, api, customer):
        device = issue_tokens(customer)
        body = {"current_password": PASSWORD, "new_password": "Papaya2027z", "confirm_password": "Papaya2027z"}
        assert api.post(CHANGE_PASSWORD, body, format="json", **bearer(device["access"])).status_code == 200

        customer.refresh_from_db()
        customer.set_password("Guava2028q")
        customer.save()

        assert _refresh(api, device["refresh"]).status_code == 401


@pytest.mark.django_db
class TestRefreshTokenReuseDetection:
    def test_reusing_a_rotated_refresh_token_ends_the_whole_session(self, api, customer):
        original = issue_tokens(customer)
        rotated = _refresh(api, original["refresh"]).json()["data"]

        replay = _refresh(api, original["refresh"])

        assert (replay.status_code, replay.json()["code"]) == (401, "TOKEN_INVALID")
        assert _refresh(api, rotated["refresh"]).status_code == 401
        assert api.get(ME, **bearer(rotated["access"])).status_code == 401


@pytest.mark.django_db
class TestFailOpenOnlyForOutages:
    def test_misconfigured_revocation_store_is_not_silently_ignored(self, api, customer):
        access = issue_tokens(customer)["access"]

        with mock.patch("accounts.auth.sessions._store", side_effect=InvalidCacheBackendError("no 'blacklist' alias")):
            response = api.get(ME, **bearer(access))

        assert response.status_code == 500


@pytest.mark.django_db
class TestRevokedTokensRevealNothing:
    def test_revoked_session_does_not_leak_the_lock_reason(self, api, customer):
        tokens = issue_tokens(customer)
        api.post(LOGOUT, {"refresh": tokens["refresh"]}, format="json", **bearer(tokens["access"]))
        customer.is_active = False
        customer.save()
        customer.customer_profile.deactivation_reason = "Repeated no-shows"
        customer.customer_profile.save()

        response = _refresh(api, tokens["refresh"])

        assert (response.status_code, response.json()["code"]) == (401, "TOKEN_INVALID")
        assert "reason" not in response.json()["errors"]


LOCAL_CACHES = {
    "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
    "blacklist": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": "blacklist"},
}


class TestRevocationStoreSystemCheck:
    def test_process_local_store_is_an_error_outside_debug(self):
        with override_settings(DEBUG=False, CACHES=LOCAL_CACHES):
            errors = check_token_revocation_store(None)

        assert [error.id for error in errors] == ["accounts.E001"]

    def test_process_local_store_is_fine_for_local_debugging(self):
        with override_settings(DEBUG=True, CACHES=LOCAL_CACHES):
            assert check_token_revocation_store(None) == []

    def test_redis_store_passes(self):
        caches = {
            "default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"},
            "blacklist": {"BACKEND": "django_redis.cache.RedisCache", "LOCATION": "redis://127.0.0.1:6379/15"},
        }
        with override_settings(DEBUG=False, CACHES=caches):
            assert check_token_revocation_store(None) == []
