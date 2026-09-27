from django.core.cache import caches
from django.db import connection
from django.utils import timezone
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from accounts.auth.tokens import SESSION_CLAIM
from marketlink_core.exceptions import ErrorCode
from marketlink_core.permissions import IsCustomerOrFarmer
from marketlink_core.responses import api_response
from marketlink_core.services.ws_ticket import DEFAULT_TTL, create_ws_ticket


def _database_status() -> str:
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:  # noqa: BLE001 - any failure means the database is unreachable
        return "error"
    return "ok"


def _cache_status() -> str:
    try:
        cache = caches["default"]
        cache.set("health:ping", "ok", 5)
        return "ok" if cache.get("health:ping") == "ok" else "error"
    except Exception:  # noqa: BLE001 - report the cache as down instead of failing the probe
        return "error"


# No auth or throttling so uptime monitors are never rejected; only the database decides 200 vs 503.
class HealthCheckView(APIView):
    permission_classes = [AllowAny]
    authentication_classes: list = []
    throttle_classes: list = []

    @extend_schema(
        responses={
            200: OpenApiResponse(description="Envelope with data: {database, cache, time}."),
            503: OpenApiResponse(description="The database is unreachable."),
        },
        summary="Service health probe",
    )
    def get(self, request):
        database = _database_status()
        data = {
            "status": "ok" if database == "ok" else "error",
            "database": database,
            "cache": _cache_status(),
            "time": timezone.localtime().isoformat(),
        }
        if database == "ok":
            return api_response(message="OK", data=data, request=request)
        return api_response(
            message="Service unavailable.",
            data=data,
            status_code=503,
            code=ErrorCode.INTERNAL_SERVER_ERROR,
            request=request,
        )


class WebSocketTicketView(APIView):
    """AU-08: one-time ticket for /ws/notifications/ (Customer, Farmer only)."""

    permission_classes = [IsCustomerOrFarmer]

    @extend_schema(
        request=None,
        responses={200: OpenApiResponse(description="Envelope with data: {ticket, expires_in}."), 401: None, 403: None},
        summary="One-time WebSocket ticket",
    )
    def post(self, request):
        role_code = getattr(getattr(request.user, "role", None), "code", "")
        session_id = request.auth.get(SESSION_CLAIM) if request.auth is not None else None
        ticket = create_ws_ticket(user_id=request.user.pk, role=role_code, session_id=session_id)
        return api_response(
            message="Ticket generated.",
            data={"ticket": ticket, "expires_in": DEFAULT_TTL},
            request=request,
        )
