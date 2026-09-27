import uuid

import pytest
from django.db import OperationalError
from django.test import RequestFactory
from rest_framework.response import Response
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.views import APIView

from marketlink_core.exceptions import BusinessValidationError, ConflictError, PreconditionRequiredError
from marketlink_core.http import require_idempotency_key
from marketlink_core.permissions import IsCustomer
from marketlink_core.services.db_retry import run_with_deadlock_retry
from system.models import AuditLog
from tests_support.factories import make_customer, make_farmer


class TestDeadlockRetry:
    def test_retries_once_after_deadlock(self):
        calls = []

        def work():
            calls.append(1)
            if len(calls) == 1:
                raise OperationalError(1213, "Deadlock found")
            return "done"

        assert run_with_deadlock_retry(work) == "done"
        assert len(calls) == 2

    def test_second_deadlock_becomes_conflict_retry(self):
        def work():
            raise OperationalError(1213, "Deadlock found")

        with pytest.raises(ConflictError) as caught:
            run_with_deadlock_retry(work)
        assert caught.value.code == "CONFLICT_RETRY"

    def test_lock_wait_timeout_is_not_retried(self):
        # It already waited innodb_lock_wait_timeout; the exception handler turns it into 409.
        calls = []

        def work():
            calls.append(1)
            raise OperationalError(1205, "Lock wait timeout exceeded")

        with pytest.raises(OperationalError):
            run_with_deadlock_retry(work)
        assert len(calls) == 1

    def test_lock_wait_timeout_reaches_the_client_as_conflict_retry(self):
        class _BusyView(APIView):
            authentication_classes = []
            permission_classes = []

            def post(self, request):
                return run_with_deadlock_retry(self._locked)

            @staticmethod
            def _locked():
                raise OperationalError(1205, "Lock wait timeout exceeded")

        response = _BusyView.as_view()(APIRequestFactory().post("/busy/"))

        assert (response.status_code, response.data["code"]) == (409, "CONFLICT_RETRY")

    def test_other_database_errors_propagate(self):
        def work():
            raise OperationalError(2006, "MySQL server has gone away")

        with pytest.raises(OperationalError):
            run_with_deadlock_retry(work)


class TestIdempotencyKeyHeader:
    def test_missing_header_requires_precondition(self):
        with pytest.raises(PreconditionRequiredError):
            require_idempotency_key(RequestFactory().post("/"))

    def test_malformed_header_is_a_validation_error(self):
        request = RequestFactory().post("/", HTTP_IDEMPOTENCY_KEY="not-a-uuid")

        with pytest.raises(BusinessValidationError):
            require_idempotency_key(request)

    def test_valid_uuid_is_normalised(self):
        key = uuid.uuid4()
        request = RequestFactory().post("/", HTTP_IDEMPOTENCY_KEY=str(key).upper())

        assert require_idempotency_key(request) == str(key)


class _CustomerOnlyView(APIView):
    permission_classes = [IsCustomer]

    def get(self, request):
        return Response({"ok": True})


def _get(user=None):
    request = APIRequestFactory().get("/api/customer/probe/")
    if user is not None:
        force_authenticate(request, user=user)
    return _CustomerOnlyView.as_view()(request)


@pytest.mark.django_db
class TestIsCustomer:
    def test_customer_is_allowed(self):
        assert _get(make_customer()).status_code == 200

    def test_other_role_gets_403_and_is_audited(self):
        farmer_user = make_farmer().user

        response = _get(farmer_user)

        assert (response.status_code, response.data["code"]) == (403, "PERMISSION_DENIED")
        log = AuditLog.objects.get(action="ACCESS_DENIED")
        assert (log.user_id, log.status_code, log.endpoint) == (farmer_user.id, 403, "/api/customer/probe/")

    def test_anonymous_gets_401_without_audit(self):
        assert _get().status_code == 401
        assert not AuditLog.objects.exists()
