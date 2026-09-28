from calendar import monthrange
from collections import Counter
from datetime import date, datetime, time, timedelta

from django.db.models import Count
from django.utils import timezone

from accounts.models import CustomerProfile, FarmerProfile, FarmerStatus
from accounts.selectors import list_pending_farmers
from marketlink_core.policies.roles import RoleCode
from markets.models import FarmerMarket, FarmerMarketStatus, Market
from accounts.selectors import list_customers_for_admin
from catalog.models import Product, ReviewStatus
from orders.models import Order, OrderStatus
from marketlink_core.exceptions import BusinessValidationError
from system.flags import open_flags

DASHBOARD_DAYS = 30
PENDING_FARMER_LIMIT = 5
MONTH_FORMAT = "%Y-%m"
# The platform did not exist before this, and a month a year ahead is a typo rather than a
# question. Bounds stop a hand-typed ?month= from asking for year 9999.
EARLIEST_YEAR = 2024


def _orders_per_day(*, days: int) -> list[dict]:
    last_day = timezone.localdate()
    first_day = last_day - timedelta(days=days - 1)
    counts = _count_by_day(first_day, last_day)
    days_range = [first_day + timedelta(days=offset) for offset in range(days)]
    return [{"date": day, "count": counts.get(day, 0)} for day in days_range]


def _count_by_day(first_day: date, last_day: date) -> Counter:
    # TruncDate and __date lookups compile to CONVERT_TZ, which returns NULL unless the MySQL
    # timezone tables are loaded, so the window is a datetime range and the buckets are
    # counted in Python.
    window_start = timezone.make_aware(datetime.combine(first_day, time.min))
    window_end = timezone.make_aware(datetime.combine(last_day + timedelta(days=1), time.min))
    stamps = Order.objects.filter(
        created_at__gte=window_start, created_at__lt=window_end
    ).values_list("created_at", flat=True)
    return Counter(timezone.localtime(stamp).date() for stamp in stamps)


def month_bounds(raw: str | None) -> date:
    """Read a ``YYYY-MM`` parameter, or fall back to the month we are in."""
    today = timezone.localdate()
    if not raw:
        return today.replace(day=1)
    try:
        parsed = datetime.strptime(raw.strip(), MONTH_FORMAT).date()
    except ValueError as exc:
        raise BusinessValidationError(
            "That is not a month.",
            errors={"month": ["Use YYYY-MM, for example 2026-09."]},
        ) from exc
    if not EARLIEST_YEAR <= parsed.year <= today.year + 1:
        raise BusinessValidationError(
            "That month is outside the range the platform has data for.",
            errors={"month": [f"Choose a month between {EARLIEST_YEAR} and {today.year + 1}."]},
        )
    return parsed.replace(day=1)


def orders_per_month(*, first_day: date) -> dict:
    """One bucket per day of a calendar month, zeros included.

    A calendar month rather than a rolling window, because the buttons on the dashboard step
    month by month and a rolling window cannot be stepped through without the days sliding.
    """
    length = monthrange(first_day.year, first_day.month)[1]
    last_day = first_day.replace(day=length)
    counts = _count_by_day(first_day, last_day)
    days = [first_day + timedelta(days=offset) for offset in range(length)]
    return {
        "month": first_day.strftime(MONTH_FORMAT),
        "total": sum(counts.values()),
        "days": [{"date": day, "count": counts.get(day, 0)} for day in days],
    }


def orders_by_status(*, queryset=None) -> list[dict]:
    # Every status is listed, zeros included, so the bar chart keeps a stable shape.
    source = Order.objects.all() if queryset is None else queryset
    counts = dict(
        source.values("status").annotate(total=Count("id")).values_list("status", "total")
    )
    return [{"status": status, "count": counts.get(status, 0)} for status in OrderStatus.values]


def dashboard_snapshot() -> dict:
    return {
        "totals": {
            "farmers": FarmerProfile.objects.count(),
            "farmers_pending": FarmerProfile.objects.filter(status=FarmerStatus.PENDING).count(),
            "customers": CustomerProfile.objects.filter(user__role__code=RoleCode.CUSTOMER).count(),
            "markets_active": Market.objects.filter(is_active=True).count(),
            "orders": Order.objects.count(),
        },
        # Counts alone say how the platform is doing; these say what is waiting for someone.
        "needs_attention": _needs_attention(),
        "orders_by_day": _orders_per_day(days=DASHBOARD_DAYS),
        "orders_by_status": orders_by_status(),
        "pending_farmers": list_pending_farmers(limit=PENDING_FARMER_LIMIT),
    }


def approval_counts() -> dict:
    stalls = FarmerProfile.objects.filter(status=FarmerStatus.PENDING).count()
    products = Product.objects.filter(review_status=ReviewStatus.PENDING).count()
    markets = FarmerMarket.objects.filter(status=FarmerMarketStatus.PENDING).count()
    return {"stalls": stalls, "products": products, "markets": markets, "total": stalls + products + markets}


def _needs_attention() -> dict:
    """The work queue. Every number here is something an admin can act on today."""
    return {
        "stalls_awaiting_approval": FarmerProfile.objects.filter(
            status=FarmerStatus.PENDING
        ).count(),
        "products_awaiting_approval": Product.objects.filter(
            review_status=ReviewStatus.PENDING, is_archived=False
        ).count(),
        "market_requests_awaiting_approval": FarmerMarket.objects.filter(
            status=FarmerMarketStatus.PENDING
        ).count(),
        "flags_open": open_flags().count(),
        "customers_at_risk": list_customers_for_admin(at_risk=True).count(),
        "hidden_products": Product.objects.filter(is_hidden_by_admin=True).count(),
        # Markets closed while stalls still list them, which strands those stalls.
        "markets_closed": Market.objects.filter(is_active=False).count(),
    }
