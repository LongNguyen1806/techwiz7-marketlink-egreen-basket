from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.admin_portal.serializers_admin import (
    AdminCustomerDetailSerializer,
    AdminCustomerEditSerializer,
    AdminCustomerRowSerializer,
    AdminReasonSerializer,
    DeactivationImpactSerializer,
)
from accounts.selectors import customer_for_admin, list_customers_for_admin
from accounts.services.customer_status_service import (
    activate_customer,
    customer_exists,
    deactivate_customer,
    deactivation_impact,
)
from marketlink_core.exceptions import ResourceNotFoundError
from marketlink_core.permissions import IsAdmin
from marketlink_core.responses import api_response
from orders.admin_selectors import recent_order_ids
from orders.customer.serializers_customer import OrderSummaryReadSerializer
from orders.selectors import order_summary_queryset
from system.models import AuditAction
from django.http import StreamingHttpResponse
from drf_spectacular.types import OpenApiTypes

from system.csv_export import CSV_CONTENT_TYPE, stream_csv
from system.services import log_request_event
from accounts.selectors import ADMIN_CUSTOMER_ORDERING
from accounts.services.profile_admin_service import update_customer_profile

RECENT_ORDER_LIMIT = 10


def _require_customer(customer_id: int) -> int:
    if not customer_exists(customer_id=customer_id):
        raise ResourceNotFoundError("Customer not found.")
    return customer_id


def _flag(raw: str | None) -> bool | None:
    if raw is None:
        return None
    lowered = raw.strip().lower()
    if lowered in ("true", "1"):
        return True
    if lowered in ("false", "0"):
        return False
    return None


class AdminCustomerListView(ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = AdminCustomerRowSerializer

    def get_queryset(self):
        params = self.request.query_params
        return list_customers_for_admin(
            is_active=_flag(params.get("is_active")),
            q=params.get("q"),
            at_risk=_flag(params.get("at_risk")),
            ordering=params.get("ordering"),
        )

    @extend_schema(
        parameters=[
            OpenApiParameter("is_active", bool),
            OpenApiParameter("q", str, description="Matches the name, email or phone."),
            OpenApiParameter("at_risk", bool, description="D-028 repeat no-show flag."),
            OpenApiParameter(
                "ordering",
                str,
                enum=sorted(ADMIN_CUSTOMER_ORDERING),
                description="Sort column; prefix with - for descending.",
            ),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AdminCustomerDetailView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(responses={200: AdminCustomerDetailSerializer, 404: None})
    def get(self, request, id: int) -> Response:
        _require_customer(id)
        profile = customer_for_admin(customer_id=id)
        order_ids = recent_order_ids(customer_id=id, limit=RECENT_ORDER_LIMIT)
        recent = OrderSummaryReadSerializer(
            order_summary_queryset(order_ids).order_by("-created_at", "-id"), many=True
        ).data
        serializer = AdminCustomerDetailSerializer(profile, context={"recent_orders": recent})
        return api_response(message="OK", request=request, data=serializer.data)

    @extend_schema(
        request=AdminCustomerEditSerializer,
        responses={200: AdminCustomerRowSerializer, 400: None, 404: None},
        summary="Correct a shopper's contact details",
    )
    def patch(self, request, id: int) -> Response:
        _require_customer(id)
        serializer = AdminCustomerEditSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        profile, changed = update_customer_profile(
            customer_id=id, validated=dict(serializer.validated_data), actor=request.user
        )
        if changed:
            log_request_event(
                request,
                action=AuditAction.CUSTOMER_UPDATED,
                status_code=200,
                details={"customer_id": id, "changed_fields": changed},
            )
        return api_response(
            message="Customer updated." if changed else "Nothing to update.",
            request=request,
            data=AdminCustomerRowSerializer(customer_for_admin(customer_id=profile.pk)).data,
        )


class AdminCustomerDeactivationImpactView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(responses={200: DeactivationImpactSerializer, 404: None})
    def get(self, request, id: int) -> Response:
        _require_customer(id)
        data = DeactivationImpactSerializer(deactivation_impact(customer_id=id)).data
        return api_response(message="OK", request=request, data=data)


class _CustomerActionView(APIView):
    permission_classes = [IsAdmin]

    def _row(self, request, customer_id: int, *, message: str, extra: dict | None = None) -> Response:
        data = AdminCustomerRowSerializer(customer_for_admin(customer_id=customer_id)).data
        if extra:
            data.update(extra)
        return api_response(message=message, request=request, data=data)

    def _audit(self, request, *, action: str, customer_id: int, details: dict) -> None:
        # Written after the business transaction so a rollback cannot erase the trail.
        log_request_event(
            request,
            action=action,
            status_code=200,
            details={"customer_id": customer_id, **details},
        )


class AdminCustomerDeactivateView(_CustomerActionView):
    @extend_schema(
        request=AdminReasonSerializer,
        responses={200: AdminCustomerRowSerializer, 400: None, 404: None},
        summary="Lock a customer and cancel every open order",
    )
    def post(self, request, id: int) -> Response:
        _require_customer(id)
        serializer = AdminReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reason = serializer.validated_data["reason"]
        _, affected_orders = deactivate_customer(
            customer_id=id, reason=reason, actor=request.user
        )
        self._audit(
            request,
            action=AuditAction.CUSTOMER_DEACTIVATED,
            customer_id=id,
            details={"reason": reason, "affected_orders": affected_orders},
        )
        return self._row(
            request, id, message="Customer locked.", extra={"affected_orders": affected_orders}
        )


class AdminCustomerActivateView(_CustomerActionView):
    @extend_schema(
        request=None, responses={200: AdminCustomerRowSerializer, 400: None, 404: None}
    )
    def post(self, request, id: int) -> Response:
        activate_customer(customer_id=_require_customer(id))
        self._audit(request, action=AuditAction.CUSTOMER_ACTIVATED, customer_id=id, details={})
        return self._row(request, id, message="Customer activated.")


class AdminCustomerExportView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        responses={(200, CSV_CONTENT_TYPE): OpenApiTypes.BINARY},
        summary="Download the customer list as CSV",
    )
    def get(self, request) -> StreamingHttpResponse:
        params = request.query_params
        customers = list_customers_for_admin(
            is_active=_flag(params.get("is_active")),
            q=params.get("q"),
            at_risk=_flag(params.get("at_risk")),
            ordering=params.get("ordering"),
        ).select_related("user")

        log_request_event(
            request,
            action=AuditAction.EXPORT_DATA,
            status_code=200,
            details={"export": "customers", "row_count": customers.count()},
        )
        return stream_csv(
            filename="customers",
            headers=[
                "id", "full_name", "phone", "email", "date_joined", "is_active",
                "total_orders", "open_orders", "no_show_count", "at_risk",
            ],
            rows=(
                [
                    c.user_id, c.full_name, c.phone, c.user.email, c.user.date_joined.date(),
                    c.user.is_active, c.total_orders, c.open_orders, c.no_show_count, c.at_risk,
                ]
                for c in customers
            ),
        )
