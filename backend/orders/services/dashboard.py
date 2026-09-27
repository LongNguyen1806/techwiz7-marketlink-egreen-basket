"""FA-01 / F-01: farmer dashboard figures (FR-46).

Decisions v1.8:
- D1: the date range is on pickup_date (cash is paid at pickup, so sales happen that day).
- D2: total_orders, revenue, revenue_by_day and top_products follow the range; pending_approval,
  in_progress, overdue_open_count and upcoming show the current state (same numbers as F-02).
- D3: upcoming = open orders (PLACED, ACCEPTED, READY) whose pickup has not ended, nearest first.
- D4: from <= to, at most 366 days; revenue_by_day lists every day of the range (0 when none).
"""

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal
from typing import Any

from django.db.models import Max, QuerySet, Sum
from django.utils import timezone

from accounts.models import FarmerProfile
from catalog.models import Product
from marketlink_core.exceptions import BusinessValidationError
from orders.models import OPEN_STATUSES, Order, OrderItem, OrderStatus

DEFAULT_RANGE_DAYS = 7
MAX_RANGE_DAYS = 366
TOP_PRODUCTS_LIMIT = 5
UPCOMING_LIMIT = 5
IN_PROGRESS_STATUSES = (OrderStatus.ACCEPTED, OrderStatus.READY_FOR_PICKUP)
ZERO = Decimal("0.00")


@dataclass(frozen=True)
class DateRange:
    date_from: date
    date_to: date

    def days(self) -> list[date]:
        return [self.date_from + timedelta(days=offset) for offset in range((self.date_to - self.date_from).days + 1)]


def _parse(raw: str | None, name: str, errors: dict[str, list[str]]) -> date | None:
    if raw in (None, ""):
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        errors[name] = ["Use the YYYY-MM-DD format."]
        return None


def resolve_date_range(raw_from: str | None, raw_to: str | None) -> DateRange:
    """Default: the last 7 days up to today (local date)."""
    errors: dict[str, list[str]] = {}
    parsed_from, parsed_to = _parse(raw_from, "from", errors), _parse(raw_to, "to", errors)
    if errors:
        raise BusinessValidationError("Invalid query parameters.", errors=errors)

    date_to = parsed_to or timezone.localdate()
    date_from = parsed_from or date_to - timedelta(days=DEFAULT_RANGE_DAYS - 1)
    if date_from > date_to:
        raise BusinessValidationError(
            "Invalid query parameters.", errors={"from": ["The start date must be on or before the end date."]}
        )
    if (date_to - date_from).days + 1 > MAX_RANGE_DAYS:
        raise BusinessValidationError(
            "Invalid query parameters.", errors={"from": [f"The range can be at most {MAX_RANGE_DAYS} days."]}
        )
    return DateRange(date_from=date_from, date_to=date_to)


def _money(value: Decimal | None) -> str:
    return str((value or ZERO).quantize(Decimal("0.01")))


def _top_products(completed: QuerySet) -> list[dict[str, Any]]:
    rows = list(
        OrderItem.objects.filter(order__in=completed)
        .values("product_id")
        .annotate(quantity_sold=Sum("quantity"), revenue=Sum("line_total"), snapshot_name=Max("product_name"))
        .order_by("-quantity_sold", "-revenue", "product_id")[:TOP_PRODUCTS_LIMIT]
    )
    names = Product.objects.in_bulk([row["product_id"] for row in rows])
    return [
        {
            "product_id": row["product_id"],
            # Current product name (decision v1.8); the order snapshot is only a fallback.
            "name": names[row["product_id"]].name if row["product_id"] in names else row["snapshot_name"],
            "quantity_sold": row["quantity_sold"],
            "revenue": _money(row["revenue"]),
        }
        for row in rows
    ]


def build_farmer_dashboard(*, farmer: FarmerProfile, date_range: DateRange) -> dict[str, Any]:
    """Figures only; the caller runs the lazy sweep first (D-009) and serializes `upcoming`."""
    now = timezone.now()
    orders = Order.objects.filter(farmer=farmer)

    in_range = orders.filter(pickup_date__gte=date_range.date_from, pickup_date__lte=date_range.date_to)
    completed = in_range.filter(status=OrderStatus.COMPLETED)
    revenue_rows = dict(
        completed.values("pickup_date").annotate(total=Sum("total_amount")).values_list("pickup_date", "total")
    )

    return {
        "kpis": {
            "total_orders": in_range.count(),
            "pending_approval": orders.filter(status=OrderStatus.PLACED).count(),
            "in_progress": orders.filter(status__in=IN_PROGRESS_STATUSES).count(),
            "revenue": _money(completed.aggregate(total=Sum("total_amount"))["total"]),
        },
        "revenue_by_day": [
            {"date": day.isoformat(), "revenue": _money(revenue_rows.get(day))} for day in date_range.days()
        ],
        "top_products": _top_products(completed),
        "overdue_open_count": orders.filter(status__in=IN_PROGRESS_STATUSES, pickup_end_at__lte=now).count(),
        # Loaded with the relations OrderSummary needs; serialized by the view.
        "upcoming": list(
            orders.filter(status__in=OPEN_STATUSES, pickup_end_at__gt=now)
            .select_related("customer__customer_profile", "farmer", "market")
            .prefetch_related("items__product")
            .order_by("pickup_start_at", "id")[:UPCOMING_LIMIT]
        ),
        "status": farmer.status,
        "status_reason": farmer.status_reason,
        "range": {"from": date_range.date_from.isoformat(), "to": date_range.date_to.isoformat()},
    }
