from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.admin_portal.serializers_admin import AdminReasonSerializer
from accounts.geocoding import geocode_address
from marketlink_core.exceptions import BusinessValidationError, ResourceNotFoundError
from marketlink_core.permissions import IsAdmin
from marketlink_core.responses import api_response
from markets.admin_portal.serializers_admin import (
    ClosureSerializer,
    MarketCloseSerializer,
    ClosureWriteSerializer,
    MarketAdminReadSerializer,
    MarketAdminWriteSerializer,
    MarketEditImpactSerializer,
    MarketGeocodeSerializer,
    MarketRequestSerializer,
)
from markets.models import Market, MarketClosure
from markets.selectors import (
    ADMIN_MARKET_ORDERING,
    MARKET_REQUEST_ORDERING,
    get_market_for_admin,
    list_closures,
    list_market_requests_for_admin,
    list_markets_for_admin,
)
from markets.services.closure_service import create_closure, delete_closure
from markets.services.farmer_schedule import approve_market_request, reject_market_request
from markets.services.market_service import (
    activate_market,
    create_market,
    deactivate_market,
    preview_market_update,
    update_market,
)
from system.models import AuditAction
from system.services import log_request_event


def _flag(raw: str | None) -> bool | None:
    if raw is None:
        return None
    lowered = raw.strip().lower()
    if lowered in ("true", "1"):
        return True
    if lowered in ("false", "0"):
        return False
    return None


def _confirmed(raw) -> bool:
    return raw is True or str(raw).strip().lower() in ("true", "1")


def _require_market(market_id: int) -> int:
    if not Market.objects.filter(pk=market_id).exists():
        raise ResourceNotFoundError("Market not found.")
    return market_id


class MarketListCreateView(ListCreateAPIView):
    permission_classes = [IsAdmin]

    def get_queryset(self):
        params = self.request.query_params
        return list_markets_for_admin(
            q=params.get("q"),
            is_active=_flag(params.get("is_active")),
            ordering=params.get("ordering"),
        )

    def get_serializer_class(self):
        return (
            MarketAdminWriteSerializer
            if self.request.method == "POST"
            else MarketAdminReadSerializer
        )

    @extend_schema(
        parameters=[
            OpenApiParameter("q", str, description="Matches the market name or address."),
            OpenApiParameter("is_active", bool, description="Filter by activation state."),
            OpenApiParameter(
                "ordering",
                str,
                enum=sorted(ADMIN_MARKET_ORDERING),
                description="Sort column; prefix with - for descending.",
            ),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        market = create_market(validated=dict(serializer.validated_data))
        log_request_event(
            request,
            action=AuditAction.MARKET_CREATED,
            status_code=201,
            details={"market_id": market.pk, "name": market.name},
        )
        return api_response(
            message="Market created.",
            request=request,
            data=MarketAdminReadSerializer(get_market_for_admin(market_id=market.pk)).data,
            status_code=201,
        )


class MarketDetailView(RetrieveUpdateAPIView):
    permission_classes = [IsAdmin]
    lookup_url_kwarg = "id"
    http_method_names = ["get", "patch", "head", "options"]

    def get_queryset(self):
        return list_markets_for_admin()

    def get_serializer_class(self):
        return (
            MarketAdminWriteSerializer
            if self.request.method == "PATCH"
            else MarketAdminReadSerializer
        )

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return api_response(message="OK", request=request, data=serializer.data)

    def update(self, request, *args, **kwargs):
        market = self.get_object()
        serializer = self.get_serializer(market, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        _, impact = update_market(
            market_id=market.pk,
            validated=dict(serializer.validated_data),
            actor=request.user,
            confirm_affected=_confirmed(request.data.get("confirm_affected_orders")),
        )
        summary = impact.summary()
        log_request_event(
            request,
            action=AuditAction.MARKET_UPDATED,
            status_code=200,
            details={
                "market_id": market.pk,
                "changed_fields": summary["changed_fields"],
                "deactivated_slot_count": summary["slots_to_disable"],
                "orders_to_reschedule": summary["orders_to_reschedule"],
                "notified": summary["customers_to_notify"] + summary["stalls_to_notify"],
            },
        )
        data = MarketAdminReadSerializer(get_market_for_admin(market_id=market.pk)).data
        data["deactivated_slot_count"] = summary["slots_to_disable"]
        data["orders_to_reschedule"] = summary["orders_to_reschedule"]
        data["notified"] = summary["customers_to_notify"] + summary["stalls_to_notify"]
        return api_response(message="Market updated.", request=request, data=data)


class MarketGeocodeView(APIView):
    """Where an address is, so the market form can drop its pin there.

    Looked up here rather than in the browser: Nominatim allows one request a second for the
    whole app and wants the app named in the User-Agent, and accounts.geocoding already
    does both (D-032). The admin still drags the pin to the exact spot before saving.
    """

    permission_classes = [IsAdmin]

    @extend_schema(
        parameters=[OpenApiParameter("q", str, required=True, description="The address.")],
        responses={200: MarketGeocodeSerializer, 400: None},
        summary="Find the coordinates of an address",
    )
    def get(self, request) -> Response:
        query = (request.query_params.get("q") or "").strip()
        if len(query) < 5:
            raise BusinessValidationError(
                errors={"q": ["Type at least 5 characters of the address."]}
            )
        found = geocode_address(query)
        data = {"found": found is not None, "latitude": None, "longitude": None}
        if found is not None:
            data["latitude"], data["longitude"] = float(found[0]), float(found[1])
        return api_response(message="OK", request=request, data=data)


class MarketEditImpactView(APIView):
    """What a save would do, without saving: the admin confirms these numbers first."""

    permission_classes = [IsAdmin]

    @extend_schema(
        request=MarketAdminWriteSerializer,
        responses={200: MarketEditImpactSerializer, 400: None, 404: None},
        summary="Preview what editing a market would change",
    )
    def post(self, request, id: int) -> Response:
        market = Market.objects.filter(pk=id).first()
        if market is None:
            raise ResourceNotFoundError("Market not found.")
        serializer = MarketAdminWriteSerializer(market, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        impact = preview_market_update(
            market=market, validated=dict(serializer.validated_data)
        )
        return api_response(message="OK", request=request, data=impact.summary())


class _MarketStateView(APIView):
    permission_classes = [IsAdmin]

    def _audit(self, request, *, action: str, market_id: int, extra: dict | None = None) -> None:
        log_request_event(
            request,
            action=action,
            status_code=200,
            details={"market_id": market_id, **(extra or {})},
        )

    def _respond(self, request, *, market_id: int, message: str) -> Response:
        return api_response(
            message=message,
            request=request,
            data=MarketAdminReadSerializer(get_market_for_admin(market_id=market_id)).data,
        )


class MarketDeactivateView(_MarketStateView):
    @extend_schema(
        request=MarketCloseSerializer,
        responses={200: MarketAdminReadSerializer, 400: None, 404: None},
        summary="Close a market",
    )
    def post(self, request, id: int) -> Response:
        _require_market(id)
        serializer = MarketCloseSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"]
        farmer_message = serializer.validated_data.get("farmer_message", "")

        _, cancelled = deactivate_market(
            market_id=id, reason=reason, actor=request.user, farmer_message=farmer_message
        )
        self._audit(
            request,
            action=AuditAction.MARKET_DEACTIVATED,
            market_id=id,
            extra={
                "reason": reason,
                "cancelled_orders": cancelled,
                "emailed_note": bool(farmer_message),
            },
        )
        data = MarketAdminReadSerializer(get_market_for_admin(market_id=id)).data
        data["cancelled_orders"] = cancelled
        return api_response(message="Market closed.", request=request, data=data)


class MarketActivateView(_MarketStateView):
    @extend_schema(
        request=None,
        responses={200: MarketAdminReadSerializer, 404: None},
        summary="Activate a market",
    )
    def post(self, request, id: int) -> Response:
        _, restored = activate_market(market_id=_require_market(id))
        self._audit(
            request,
            action=AuditAction.MARKET_ACTIVATED,
            market_id=id,
            extra={"restored_slots": restored},
        )
        data = MarketAdminReadSerializer(get_market_for_admin(market_id=id)).data
        data["restored_slots"] = restored
        return api_response(message="Market reopened.", request=request, data=data)


class MarketRequestListView(ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = MarketRequestSerializer

    def get_queryset(self):
        params = self.request.query_params
        market_id = params.get("market_id")
        return list_market_requests_for_admin(
            q=params.get("q"),
            market_id=int(market_id) if market_id and market_id.isdigit() else None,
            ordering=params.get("ordering"),
        )

    @extend_schema(
        parameters=[
            OpenApiParameter("q", str, description="Matches the stall name, email or phone."),
            OpenApiParameter("market_id", int, description="Only requests for this market."),
            OpenApiParameter(
                "ordering",
                str,
                enum=sorted(MARKET_REQUEST_ORDERING),
                description="Sort column; prefix with - for descending.",
            ),
        ],
        summary="Market registrations waiting for approval",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class MarketRequestApproveView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(request=None, responses={200: MarketRequestSerializer, 404: None, 422: None})
    def post(self, request, id: int) -> Response:
        farmer_market = approve_market_request(farmer_market_id=id, actor=request.user)
        log_request_event(
            request,
            action=AuditAction.STALL_MARKET_APPROVED,
            status_code=200,
            details={
                "farmer_market_id": id,
                "farmer_id": farmer_market.farmer_id,
                "market_id": farmer_market.market_id,
            },
        )
        return api_response(
            message="Market registration approved.",
            request=request,
            data=MarketRequestSerializer(farmer_market).data,
        )


class MarketRequestRejectView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(request=AdminReasonSerializer, responses={200: None, 400: None, 404: None, 422: None})
    def post(self, request, id: int) -> Response:
        serializer = AdminReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"]
        summary = reject_market_request(farmer_market_id=id, reason=reason, actor=request.user)
        log_request_event(
            request,
            action=AuditAction.STALL_MARKET_REJECTED,
            status_code=200,
            details={
                "farmer_market_id": id,
                "farmer_id": summary["farmer_id"],
                "market_id": summary["market_id"],
                "reason": reason,
            },
        )
        return api_response(message="Market registration refused.", request=request, data={"id": id})


class MarketClosureListCreateView(ListCreateAPIView):
    permission_classes = [IsAdmin]
    pagination_class = None
    serializer_class = ClosureSerializer

    def get_queryset(self):
        return list_closures(
            market_id=_require_market(self.kwargs["id"]),
            include_past=bool(_flag(self.request.query_params.get("include_past"))),
        )

    def get_serializer_class(self):
        return ClosureWriteSerializer if self.request.method == "POST" else ClosureSerializer

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "include_past", bool, description="Include periods that have already ended."
            )
        ]
    )
    def list(self, request, *args, **kwargs):
        serializer = ClosureSerializer(self.get_queryset(), many=True)
        return api_response(message="OK", request=request, data=serializer.data)

    def create(self, request, *args, **kwargs):
        market_id = _require_market(self.kwargs["id"])
        serializer = ClosureWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        closure = create_closure(
            market_id=market_id,
            start_date=serializer.validated_data["start_date"],
            end_date=serializer.validated_data["end_date"],
            reason=serializer.validated_data.get("reason") or None,
        )
        return api_response(
            message="Closure period added.",
            request=request,
            data=ClosureSerializer(closure).data,
            status_code=201,
        )


class MarketClosureDeleteView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(request=None, responses={204: None, 404: None}, summary="Delete a closure")
    def delete(self, request, id: int) -> Response:
        if not MarketClosure.objects.filter(pk=id).exists():
            raise ResourceNotFoundError("Closure period not found.")
        delete_closure(closure_id=id)
        return Response(status=status.HTTP_204_NO_CONTENT)
