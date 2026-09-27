import uuid
from unittest import mock

from django.conf import settings
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import resolve
from rest_framework import exceptions, status
from rest_framework.permissions import AllowAny
from rest_framework.test import APIRequestFactory
from rest_framework.views import APIView

from marketlink_core.context import get_request_id
from marketlink_core.exceptions import DomainError
from marketlink_core.middleware import RequestIDMiddleware
from marketlink_core.pagination import StandardPagination
from marketlink_core.responses import api_response

ENVELOPE_KEYS = {"success", "message", "request_id", "data", "errors"}


def _call_view(raise_exc=None, payload=None):
    class _View(APIView):
        permission_classes = [AllowAny]

        def get(self, request):
            if raise_exc is not None:
                raise raise_exc
            return api_response(data=payload, message="OK")

    request = APIRequestFactory().get("/probe/")
    return RequestIDMiddleware(lambda r: _View.as_view()(r))(request)


class TestRequestIDMiddleware:
    def test_generates_uuid_and_echoes_header(self):
        seen = {}

        def view(request):
            seen["rid"] = get_request_id()
            return HttpResponse()

        response = RequestIDMiddleware(view)(RequestFactory().get("/"))

        assert uuid.UUID(response["X-Request-ID"])
        assert seen["rid"] == response["X-Request-ID"]

    def test_reuses_valid_client_request_id(self):
        rid = str(uuid.uuid4())
        request = RequestFactory().get("/", HTTP_X_REQUEST_ID=rid)

        response = RequestIDMiddleware(lambda r: HttpResponse())(request)

        assert response["X-Request-ID"] == rid

    def test_replaces_malformed_client_request_id(self):
        request = RequestFactory().get("/", HTTP_X_REQUEST_ID="bad\nvalue")

        response = RequestIDMiddleware(lambda r: HttpResponse())(request)

        assert response["X-Request-ID"] != "bad\nvalue"
        assert uuid.UUID(response["X-Request-ID"])

    def test_is_registered(self):
        assert "marketlink_core.middleware.RequestIDMiddleware" in settings.MIDDLEWARE


class TestEnvelope:
    def test_success_envelope(self):
        response = _call_view(payload={"x": 1})

        assert response.status_code == 200
        assert set(response.data) == ENVELOPE_KEYS
        assert response.data["success"] is True
        assert response.data["data"] == {"x": 1}
        assert response.data["errors"] == {}
        assert response.data["request_id"] == response["X-Request-ID"]

    def test_validation_error_maps_to_contract(self):
        response = _call_view(exceptions.ValidationError({"email": ["bad"]}))

        assert response.status_code == 400
        assert set(response.data) == ENVELOPE_KEYS | {"code"}
        assert response.data["success"] is False
        assert response.data["code"] == "VALIDATION_ERROR"
        assert response.data["errors"] == {"email": ["bad"]}
        assert response.data["request_id"] == response["X-Request-ID"]

    def test_non_field_validation_error_uses_non_field_errors_key(self):
        response = _call_view(exceptions.ValidationError(["whole payload bad"]))

        assert response.data["errors"] == {"non_field_errors": ["whole payload bad"]}

    def test_nested_validation_errors_are_flattened_with_dots(self):
        detail = {"groups": [{"items": [{}, {"quantity": ["too many"]}]}]}

        response = _call_view(exceptions.ValidationError(detail))

        assert response.data["errors"] == {"groups.0.items.1.quantity": ["too many"]}

    def test_drf_exceptions_map_to_frozen_codes(self):
        cases = [
            (exceptions.NotAuthenticated(), 401, "NOT_AUTHENTICATED"),
            (exceptions.AuthenticationFailed(), 401, "NOT_AUTHENTICATED"),
            (exceptions.PermissionDenied(), 403, "PERMISSION_DENIED"),
            (exceptions.NotFound(), 404, "NOT_FOUND"),
            (exceptions.Throttled(wait=10), 429, "THROTTLED"),
        ]
        for exc, http_status, code in cases:
            response = _call_view(exc)
            assert (response.status_code, response.data["code"]) == (http_status, code)
            assert response.data["errors"] == {}

    def test_domain_error_carries_code_and_errors(self):
        class InsufficientStock(DomainError):
            status_code = 400
            default_code = "INSUFFICIENT_STOCK"

        response = _call_view(InsufficientStock(errors={"items.0.quantity": ["only 3"]}))

        assert response.status_code == 400
        assert response.data["code"] == "INSUFFICIENT_STOCK"
        assert response.data["errors"] == {"items.0.quantity": ["only 3"]}

    def test_domain_error_can_carry_data(self):
        class OutOfStock(DomainError):
            status_code = 400
            default_code = "INSUFFICIENT_STOCK"

        response = _call_view(OutOfStock(errors={"items.0.quantity": ["Out of stock"]}, data={"available": {"7": 0}}))

        assert response.data["data"] == {"available": {"7": 0}}
        assert response.data["errors"] == {"items.0.quantity": ["Out of stock"]}

    def test_unexpected_error_returns_500_envelope(self):
        response = _call_view(RuntimeError("boom"))

        assert response.status_code == 500
        assert response.data["code"] == "INTERNAL_SERVER_ERROR"
        assert "boom" not in response.data["message"]


class TestPagination:
    def test_page_shape_matches_contract(self):
        request = APIRequestFactory().get("/items/", {"page": 2})
        paginator = StandardPagination()

        page = paginator.paginate_queryset(list(range(45)), APIView().initialize_request(request))
        response = paginator.get_paginated_response(page)

        assert response.data["success"] is True
        assert response.data["data"] == {
            "count": 45,
            "page": 2,
            "page_size": 20,
            "total_pages": 3,
            "next": 3,
            "previous": 1,
            "results": list(range(20, 40)),
        }


class TestRoutingAndSettings:
    def test_django_admin_mounted_outside_api_admin(self):
        assert resolve("/django-admin/").app_name == "admin"

    def test_cors_exposes_contract_headers(self):
        for header in ("x-request-id", "content-disposition", "idempotent-replayed"):
            assert header in settings.CORS_EXPOSE_HEADERS

    def test_pagination_and_exception_handler_registered(self):
        rf = settings.REST_FRAMEWORK
        assert rf["DEFAULT_PAGINATION_CLASS"] == "marketlink_core.pagination.StandardPagination"
        assert rf["EXCEPTION_HANDLER"] == "marketlink_core.responses.custom_exception_handler"


class TestHealth:
    def test_health_ok_when_database_reachable(self, client):
        with mock.patch("marketlink_core.views.connection") as conn:
            conn.cursor.return_value.__enter__.return_value.execute.return_value = None
            response = client.get("/api/health/")

        body = response.json()
        assert response.status_code == 200
        assert body["data"]["status"] == "ok"
        assert body["data"]["database"] == "ok"
        assert "time" in body["data"]

    def test_health_503_when_database_down(self, client):
        with mock.patch("marketlink_core.views.connection") as conn:
            conn.cursor.side_effect = Exception("db down")
            response = client.get("/api/health/")

        assert response.status_code == 503
        assert response.json()["data"]["database"] == "error"
