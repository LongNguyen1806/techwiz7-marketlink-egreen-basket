from django.conf import settings
from django.http import HttpResponse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from marketlink_core.constants import (
    BOOKING_HORIZON_DAYS,
    MAX_PLACED_ORDERS_PER_CUSTOMER,
    MAX_UPLOAD_MB,
)
from marketlink_core.exceptions import BusinessValidationError, ResourceNotFoundError
from marketlink_core.permissions import IsAdmin
from marketlink_core.responses import api_response
from system.dashboard import dashboard_snapshot, month_bounds, orders_per_month
from system.excel import XLSX_CONTENT_TYPE, build_report_workbook, report_filename
from system.models import AuditAction, FlagTarget
from system.reports import parse_report_range, report_summary
from system.selectors import (
    AUDIT_LOG_ORDERING,
    TRACKED_MODELS,
    build_change_log,
    list_audit_logs,
)
from marketlink_core.constants import (
    BOOKING_HORIZON_DAYS,
    MAX_PLACED_ORDERS_PER_CUSTOMER,
    MAX_UPLOAD_MB,
)
from orders.admin_selectors import at_risk_threshold, at_risk_window_days
from system.flags import list_flags, raise_flag, resolve_flag, target_previews
from system.serializers import (
    AuditLogReadSerializer,
    FlagResolutionSerializer,
    ModerationFlagReadSerializer,
    ModerationFlagWriteSerializer,
    AdminSettingsSerializer,
    ChangeLogEntrySerializer,
    DashboardSerializer,
    OrdersByMonthSerializer,
    ReportSummarySerializer,
)
from system.services import log_request_event


class AuditLogListView(ListAPIView):
    serializer_class = AuditLogReadSerializer
    permission_classes = [IsAdmin]

    @extend_schema(
        parameters=[
            OpenApiParameter("action", str, enum=list(AuditAction.values)),
            OpenApiParameter("user_id", int, description="Filter to one actor."),
            OpenApiParameter("from", OpenApiTypes.DATE, description="Inclusive."),
            OpenApiParameter("to", OpenApiTypes.DATE, description="Inclusive."),
            OpenApiParameter(
                "ordering",
                str,
                enum=sorted(AUDIT_LOG_ORDERING),
                description="Sort column; prefix with - for descending.",
            ),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def get_queryset(self):
        params = self.request.query_params
        return list_audit_logs(
            action=params.get("action"),
            user_id=params.get("user_id"),
            date_from=params.get("from"),
            date_to=params.get("to"),
            ordering=params.get("ordering"),
        )


class AuditLogDetailView(RetrieveAPIView):
    serializer_class = AuditLogReadSerializer
    permission_classes = [IsAdmin]
    lookup_url_kwarg = "id"

    def get_queryset(self):
        return list_audit_logs()

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return api_response(message="OK", request=request, data=serializer.data)


REPORT_PARAMS = [
    OpenApiParameter("from", OpenApiTypes.DATE, required=True, description="Pickup date, inclusive."),
    OpenApiParameter("to", OpenApiTypes.DATE, required=True, description="Pickup date, inclusive."),
    OpenApiParameter("market_id", int, description="Limit the report to one market."),
]


class DashboardView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(responses={200: DashboardSerializer}, summary="Admin dashboard")
    def get(self, request) -> Response:
        serializer = DashboardSerializer(dashboard_snapshot())
        return api_response(message="OK", request=request, data=serializer.data)


class DashboardOrdersByMonthView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "month",
                str,
                description="Calendar month as YYYY-MM. Defaults to the current month.",
            )
        ],
        responses={200: OrdersByMonthSerializer},
        summary="Orders per day for one calendar month",
    )
    def get(self, request) -> Response:
        # Its own endpoint rather than a parameter on the dashboard: stepping through months
        # would otherwise refetch the totals, the queue and the pending stalls every click.
        first_day = month_bounds(request.query_params.get("month"))
        return api_response(
            message="OK", request=request, data=orders_per_month(first_day=first_day)
        )


class ReportSummaryView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        parameters=REPORT_PARAMS,
        responses={200: ReportSummarySerializer, 400: None},
        summary="Report summary",
    )
    def get(self, request) -> Response:
        date_from, date_to, market_id = parse_report_range(request.query_params)
        summary = report_summary(date_from=date_from, date_to=date_to, market_id=market_id)
        return api_response(
            message="OK", request=request, data=ReportSummarySerializer(summary).data
        )


class ReportExportView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        parameters=REPORT_PARAMS,
        responses={(200, XLSX_CONTENT_TYPE): OpenApiTypes.BINARY, 400: None},
        summary="Export the report to Excel",
    )
    def get(self, request) -> HttpResponse:
        date_from, date_to, market_id = parse_report_range(request.query_params)
        summary = report_summary(date_from=date_from, date_to=date_to, market_id=market_id)
        content = build_report_workbook(summary)

        # D-018 replaces the SRS reports table with one EXPORT_DATA row per download.
        log_request_event(
            request,
            action=AuditAction.EXPORT_DATA,
            status_code=200,
            details={
                "report": "admin_summary",
                "from": str(date_from),
                "to": str(date_to),
                "market_id": market_id,
            },
        )

        # AD-26 returns the file itself, so this response carries no envelope.
        filename = report_filename(date_from=date_from, date_to=date_to)
        response = HttpResponse(content, content_type=XLSX_CONTENT_TYPE)
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class PublicConfigSerializer(serializers.Serializer):
    ai_chat_enabled = serializers.BooleanField()
    booking_horizon_days = serializers.IntegerField()
    max_placed_orders_per_customer = serializers.IntegerField()
    max_upload_mb = serializers.IntegerField()


class PublicConfigView(APIView):
    permission_classes = [AllowAny]

    @extend_schema(responses={200: PublicConfigSerializer}, summary="Client bootstrap config")
    def get(self, request) -> Response:
        # D-005: one cap on unapproved PLACED orders; the per-farmer limit is gone.
        data = {
            "ai_chat_enabled": settings.AI_CHAT_ENABLED,
            "booking_horizon_days": BOOKING_HORIZON_DAYS,
            "max_placed_orders_per_customer": getattr(
                settings, "MAX_PLACED_ORDERS_PER_CUSTOMER", MAX_PLACED_ORDERS_PER_CUSTOMER
            ),
            "max_upload_mb": MAX_UPLOAD_MB,
        }
        return api_response(
            message="OK", request=request, data=PublicConfigSerializer(data).data
        )


# The audit trail (v1.8). The contract has no AD-xx row for it, so it lives at its own path
# and is read from a record's detail screen, not from the System log tab - that tab shows
# audit_logs, which is a different thing and has no before/after to show.
CHANGE_LOG_LIMIT = 50


class AdminChangeLogView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "model",
                str,
                location=OpenApiParameter.PATH,
                enum=sorted(TRACKED_MODELS),
                description="Which tracked record to read the history of.",
            ),
            OpenApiParameter("id", int, location=OpenApiParameter.PATH),
        ],
        responses={200: ChangeLogEntrySerializer(many=True), 400: None, 404: None},
        summary="How one record changed over time",
    )
    def get(self, request, model: str, id: int) -> Response:
        tracked = TRACKED_MODELS.get(model)
        if tracked is None:
            raise BusinessValidationError(
                "Unknown record type.",
                errors={"model": [f"Choose one of: {', '.join(sorted(TRACKED_MODELS))}."]},
            )
        # The record itself is not required to still exist: history rows outlive it, and a
        # slot deleted by FA-10 or an item removed by FA-34 still has a story worth reading.
        # An id that never existed has no history either, which is the 404 below.
        entries = build_change_log(tracked, id, limit=CHANGE_LOG_LIMIT)
        # A record that exists but was never saved through the history (seed data written with
        # bulk_create) simply has no changes yet; only an id that never existed is a 404.
        if not entries and not tracked.objects.filter(pk=id).exists():
            raise ResourceNotFoundError("No history for this record.")

        # build_change_log reads oldest first because that is how a history is worked out;
        # the screen wants the most recent change at the top.
        entries = list(reversed(entries))
        return api_response(
            message="OK", request=request, data=ChangeLogEntrySerializer(entries, many=True).data
        )


class AdminFlagListView(ListAPIView):
    """The follow-up queue, oldest first."""

    permission_classes = [IsAdmin]
    serializer_class = ModerationFlagReadSerializer

    def get_queryset(self):
        raw = self.request.query_params.get("resolved")
        resolved = {"true": True, "false": False}.get((raw or "").lower(), False)
        return list_flags(
            resolved=resolved,
            target_type=self.request.query_params.get("target_type"),
            q=self.request.query_params.get("q"),
        )

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        serializer = self.get_serializer(
            page, many=True, context={"target_previews": target_previews(page)}
        )
        return self.paginator.get_paginated_response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                "resolved", bool, description="Default false: the open queue."
            ),
            # Unpacked rather than list(...): this class now defines a method called `list`,
            # which shadows the builtin inside the class body.
            OpenApiParameter("target_type", str, enum=[*FlagTarget.values]),
            OpenApiParameter(
                "q", str, description="Matches the note, the resolution, or the target id."
            ),
        ],
        summary="Content waiting for a decision",
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    @extend_schema(
        request=ModerationFlagWriteSerializer,
        responses={201: ModerationFlagReadSerializer, 400: None},
        summary="Add something to the queue",
    )
    def post(self, request) -> Response:
        serializer = ModerationFlagWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        flag = raise_flag(**serializer.validated_data, actor=request.user)
        log_request_event(
            request,
            action=AuditAction.CONTENT_FLAGGED,
            status_code=201,
            details={
                "target_type": flag.target_type,
                "target_id": flag.target_id,
                "note": flag.note,
            },
        )
        return api_response(
            message="Added to the queue.",
            request=request,
            data=ModerationFlagReadSerializer(flag).data,
            status_code=201,
        )


class AdminFlagResolveView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        request=FlagResolutionSerializer,
        responses={200: ModerationFlagReadSerializer, 400: None, 404: None},
        summary="Mark a queue item as dealt with",
    )
    def post(self, request, id: int) -> Response:
        serializer = FlagResolutionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        flag = resolve_flag(
            flag_id=id, resolution=serializer.validated_data["resolution"], actor=request.user
        )
        log_request_event(
            request,
            action=AuditAction.CONTENT_FLAG_RESOLVED,
            status_code=200,
            details={
                "target_type": flag.target_type,
                "target_id": flag.target_id,
                "resolution": flag.resolution,
            },
        )
        return api_response(
            message="Marked as dealt with.",
            request=request,
            data=ModerationFlagReadSerializer(flag).data,
        )


class AdminSettingsView(APIView):
    """What limits are in force right now.

    Read only on purpose: these come from the environment, so changing one is a deploy, not a
    form submission. The screen is how an admin who is new to the platform finds out what it
    enforces - the rules are otherwise only visible by running into them.
    """

    permission_classes = [IsAdmin]

    @extend_schema(responses={200: AdminSettingsSerializer}, summary="Limits in force")
    def get(self, request) -> Response:
        data = {
            "booking_horizon_days": BOOKING_HORIZON_DAYS,
            "max_placed_orders_per_customer": MAX_PLACED_ORDERS_PER_CUSTOMER,
            "max_upload_mb": MAX_UPLOAD_MB,
            "at_risk_threshold": at_risk_threshold(),
            "at_risk_window_days": at_risk_window_days(),
        }
        return api_response(
            message="OK", request=request, data=AdminSettingsSerializer(data).data
        )
