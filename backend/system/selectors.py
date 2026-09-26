# audit_logs = the security log: who did which sensitive action (A-11, AD-29).
# The audit trail below is a different thing: how one record changed over time
# (who, when, why, old -> new), read from the django-simple-history tables (v1.8).

from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Model, QuerySet
from django.db.models.fields.files import FieldFile
from django.utils import timezone
from django.utils.dateparse import parse_date

from rest_framework import serializers

from accounts.models import FarmerProfile
from catalog.models import Product
from marketlink_core.ordering import both_directions, resolve_ordering
from markets.models import FarmerClosure, FarmerMarket, PickupSlot
from orders.models import Order, OrderItem
from system.models import AuditLog


def _local_day_start(raw_date: str | None) -> datetime | None:
    day = parse_date(raw_date) if raw_date else None
    if day is None:
        return None
    return timezone.make_aware(datetime.combine(day, time.min))


# AD-29.
AUDIT_LOG_ORDERING = both_directions(
    {
        "created_at": ("created_at",),
        "action": ("action",),
        "user": ("user__email",),
        "status_code": ("status_code",),
    },
    tiebreak=("-id",),
)
AUDIT_LOG_ORDERING["newest"] = ("-created_at", "-id")


def list_audit_logs(
    *,
    action: str | None = None,
    user_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    ordering: str | None = None,
) -> QuerySet[AuditLog]:
    queryset = AuditLog.objects.select_related("user")

    if action:
        queryset = queryset.filter(action=action.upper())
    if user_id and str(user_id).isdigit():
        queryset = queryset.filter(user_id=int(user_id))

    start = _local_day_start(date_from)
    if start is not None:
        queryset = queryset.filter(created_at__gte=start)

    end = _local_day_start(date_to)
    if end is not None:
        # `to` is inclusive, so take every row before the following midnight.
        queryset = queryset.filter(created_at__lt=end + timedelta(days=1))

    return queryset.order_by(
        *resolve_ordering(ordering, allowed=AUDIT_LOG_ORDERING, default="newest")
    )


# Key used by the Admin API / UI -> tracked model.
TRACKED_MODELS: dict[str, type[Model]] = {
    "farmer_profile": FarmerProfile,
    "product": Product,
    "order": Order,
    "order_item": OrderItem,
    "farmer_market": FarmerMarket,
    "pickup_slot": PickupSlot,
    "farmer_closure": FarmerClosure,
}
HISTORY_TYPES = {"+": "CREATED", "~": "UPDATED", "-": "DELETED"}
IGNORED_FIELDS = {"created_at", "updated_at"}
_DATETIME_FIELD = serializers.DateTimeField()


def _user(record: Any) -> dict[str, Any] | None:
    user = record.history_user
    return {"id": user.pk, "email": user.email} if user is not None else None


def _json_safe(value: Any) -> Any:
    """Coerce a model field value into something the JSON renderer accepts.

    Most values pass through untouched. FieldFile is the one that bites: rendering an empty
    ImageFieldFile raises ValueError("has no file associated with it"), which would turn a
    changed photo into a 500.
    """
    if value is None or isinstance(value, (bool, int, float, str, list, dict)):
        return value
    if isinstance(value, FieldFile):
        return value.name or None
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return str(value)


def build_change_log(model: type[Model], object_id: int) -> list[dict[str, Any]]:
    """Every change of one record, oldest first, with the changed fields (old -> new)."""
    records = list(
        model.history.filter(**{model._meta.pk.attname: object_id})
        .select_related("history_user")
        .order_by("history_date", "history_id")
    )
    entries: list[dict[str, Any]] = []
    previous = None
    for record in records:
        changes: list[dict[str, Any]] = []
        if previous is not None and record.history_type == "~":
            delta = record.diff_against(previous)
            changes = [
                {
                    "field": change.field,
                    "old": _json_safe(change.old),
                    "new": _json_safe(change.new),
                }
                for change in delta.changes
                if change.field not in IGNORED_FIELDS
            ]
        entries.append(
            {
                "history_id": record.history_id,
                "type": HISTORY_TYPES.get(record.history_type, record.history_type),
                "date": _DATETIME_FIELD.to_representation(record.history_date),
                "user": _user(record),
                "reason": record.history_change_reason,
                "request_id": getattr(record, "request_id", None),
                "changes": changes,
            }
        )
        previous = record
    return entries
