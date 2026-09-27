from django.utils import timezone
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from marketlink_core.exceptions import BusinessValidationError, ErrorCode, ResourceNotFoundError
from marketlink_core.pagination import StandardPagination
from marketlink_core.permissions import IsCustomerOrFarmer
from marketlink_core.responses import api_response
from notifications.models import Notification
from notifications.services import serialize_notification

DROPDOWN_MAX_LIMIT = 10  # N-01 bell dropdown
BOOLEAN_VALUES = {"true": True, "false": False}


class NotificationBaseView(APIView):
    """Pass 4B §4.6: Customer and Farmer only (Admin has no personal notifications -> 403)."""

    permission_classes = [IsCustomerOrFarmer]


class NotificationListView(NotificationBaseView):
    def get(self, request: Request) -> Response:
        """NO-01: paginated list; limit (1-10) returns the latest items without pagination (N-01)."""
        params = request.query_params
        errors: dict[str, list[str]] = {}

        is_read = None
        raw_is_read = (params.get("is_read") or "").strip().lower()
        if raw_is_read:
            if raw_is_read not in BOOLEAN_VALUES:
                errors["is_read"] = ["Use true or false."]
            else:
                is_read = BOOLEAN_VALUES[raw_is_read]

        limit = None
        raw_limit = (params.get("limit") or "").strip()
        if raw_limit:
            if not raw_limit.isdigit() or not 1 <= int(raw_limit) <= DROPDOWN_MAX_LIMIT:
                errors["limit"] = [f"Must be an integer from 1 to {DROPDOWN_MAX_LIMIT}."]
            else:
                limit = int(raw_limit)
        if errors:
            raise BusinessValidationError("Invalid query parameters.", errors=errors)

        qs = Notification.objects.filter(recipient=request.user).order_by("-created_at", "-id")
        if is_read is not None:
            qs = qs.filter(is_read=is_read)

        if limit is not None:
            data = [serialize_notification(item) for item in qs[:limit]]
            return api_response(message="OK", data=data, request=request)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(qs, request, view=self)
        return paginator.get_paginated_response([serialize_notification(item) for item in page])


class NotificationUnreadCountView(NotificationBaseView):
    def get(self, request: Request) -> Response:
        """NO-02."""
        count = Notification.objects.filter(recipient=request.user, is_read=False).count()
        return api_response(message="OK", data={"unread_count": count}, request=request)


class NotificationMarkReadView(NotificationBaseView):
    def post(self, request: Request, notification_id: int) -> Response:
        """NO-03: idempotent; a second call keeps the first read_at."""
        # One conditional UPDATE: no lock needed, and a concurrent read-all cannot be overwritten.
        Notification.objects.filter(pk=notification_id, recipient=request.user, is_read=False).update(
            is_read=True, read_at=timezone.now()
        )
        notification = Notification.objects.filter(pk=notification_id, recipient=request.user).first()
        if notification is None:
            raise ResourceNotFoundError("Notification not found.", code=ErrorCode.NOT_FOUND)
        return api_response(message="OK", data=serialize_notification(notification), request=request)


class NotificationMarkAllReadView(NotificationBaseView):
    def post(self, request: Request) -> Response:
        """NO-04."""
        updated = Notification.objects.filter(recipient=request.user, is_read=False).update(
            is_read=True, read_at=timezone.now()
        )
        return api_response(message="OK", data={"updated_count": updated}, request=request)
