from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.generics import ListCreateAPIView, RetrieveUpdateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from marketlink_core.exceptions import ResourceNotFoundError
from marketlink_core.permissions import IsAdmin
from marketlink_core.responses import api_response
from markets.admin_portal.serializers_admin import (
    ClosureSerializer,
    MarketCloseSerializer,
    ClosureWriteSerializer,
    MarketAdminReadSerializer,
    MarketAdminWriteSerializer,
)
from markets.models import Market, MarketClosure
from markets.selectors import (
    ADMIN_MARKET_ORDERING,
    get_market_for_admin,
    list_closures,
    list_markets_for_admin,
)
from markets.services.closure_service import create_closure, delete_closure
from markets.services.market_service import (
    activate_market,
    create_market,
    deactivate_market,
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
        # Every audit call below sits after its service returned, so the row is written only on
        # success and only once the service's own transaction has committed (v1.8, AD-15 -> AD-17).
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
        # Taken before update_market(), which pops operating_days out of the dict it is given.
        changed_fields = sorted(serializer.validated_data)
        _, deactivated_slot_count = update_market(
            market_id=market.pk, validated=dict(serializer.validated_data)
        )
        log_request_event(
            request,
            action=AuditAction.MARKET_UPDATED,
            status_code=200,
            details={
                "market_id": market.pk,
                "changed_fields": changed_fields,
                "deactivated_slot_count": deactivated_slot_count,
            },
        )
        # Re-read through the selector so the counts and prefetches are back in place.
        data = MarketAdminReadSerializer(get_market_for_admin(market_id=market.pk)).data
        data["deactivated_slot_count"] = deactivated_slot_count
        return api_response(message="Market updated.", request=request, data=data)


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
        # AD-31 returns Closure[] with no [P] marker, so data is a plain list.
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
        # 204 carries no body (Pass 4B §2.1), so this response skips the envelope.
        return Response(status=status.HTTP_204_NO_CONTENT)
