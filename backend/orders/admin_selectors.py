from datetime import timedelta

from django.conf import settings
from django.db.models import Count, Q, QuerySet
from django.utils.dateparse import parse_date

from marketlink_core.ordering import both_directions, resolve_ordering
from marketlink_core.shortcuts import get_or_404
from django.utils import timezone

from orders.models import OPEN_STATUSES, Order, OrderStatus

# D-028: EXPIRED is never counted - the order lapsed because the farmer did not confirm it
# before the pickup time, which is not the customer's fault.
AT_RISK_STATUSES = (OrderStatus.NO_SHOW,)
DEFAULT_AT_RISK_THRESHOLD = 3
DEFAULT_AT_RISK_WINDOW_DAYS = 30


def at_risk_threshold() -> int:
    # The Farmer branch owns these settings; D-028 fixes the values until they land.
    return getattr(settings, "AT_RISK_THRESHOLD", DEFAULT_AT_RISK_THRESHOLD)


def at_risk_window_days() -> int:
    return getattr(settings, "AT_RISK_WINDOW_DAYS", DEFAULT_AT_RISK_WINDOW_DAYS)


def at_risk_window_start():
    return timezone.now() - timedelta(days=at_risk_window_days())


def open_order_breakdown(queryset) -> dict:
    # Shape required by AD-04 and AD-11: one count per open status plus the total.
    rows = dict(
        queryset.filter(status__in=OPEN_STATUSES)
        .values("status")
        .annotate(total=Count("id"))
        .values_list("status", "total")
    )
    counts = {status: rows.get(status, 0) for status in OPEN_STATUSES}
    counts["total"] = sum(counts.values())
    return counts


def recent_order_ids(*, customer_id: int, limit: int) -> list[int]:
    # Materialised first: MySQL refuses a LIMIT inside IN (...) (error 1235).
    return list(
        Order.objects.filter(customer_id=customer_id)
        .order_by("-created_at", "-id")
        .values_list("id", flat=True)[:limit]
    )



# D-033 keeps the admin out of individual orders: nothing here writes. But support has to be
# able to answer "what happened to order 1234?", which needs a way to find it.
ADMIN_ORDER_ORDERING = both_directions(
    {
        "created_at": ("created_at",),
        "pickup_date": ("pickup_date",),
        "status": ("status",),
        "total_amount": ("total_amount",),
    },
    tiebreak=("-id",),
)
ADMIN_ORDER_ORDERING["newest"] = ("-created_at", "-id")


def list_orders_for_admin(
    *,
    q: str | None = None,
    status: str | None = None,
    market_id: int | None = None,
    farmer_id: int | None = None,
    customer_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    ordering: str | None = None,
) -> QuerySet[Order]:
    queryset = Order.objects.select_related(
        "customer__customer_profile", "farmer", "market"
    ).annotate(item_count=Count("items", distinct=True))

    if q:
        term = q.strip()
        lookup = (
            Q(customer__customer_profile__full_name__icontains=term)
            | Q(customer__customer_profile__phone__icontains=term)
            | Q(customer__email__icontains=term)
            | Q(farmer__stall_name__icontains=term)
        )
        # A bare number is almost always an order id someone read off a screen.
        if term.isdigit():
            lookup = lookup | Q(pk=int(term))
        queryset = queryset.filter(lookup)

    if status in OrderStatus.values:
        queryset = queryset.filter(status=status)
    if market_id is not None:
        queryset = queryset.filter(market_id=market_id)
    if farmer_id is not None:
        queryset = queryset.filter(farmer_id=farmer_id)
    if customer_id is not None:
        queryset = queryset.filter(customer_id=customer_id)

    # Filtered on pickup_date, not created_at: support is asked about the day of collection.
    start = parse_date(date_from) if date_from else None
    if start is not None:
        queryset = queryset.filter(pickup_date__gte=start)
    end = parse_date(date_to) if date_to else None
    if end is not None:
        queryset = queryset.filter(pickup_date__lte=end)

    return queryset.order_by(
        *resolve_ordering(ordering, allowed=ADMIN_ORDER_ORDERING, default="newest")
    )


def order_for_admin(*, order_id: int) -> Order:
    return get_or_404(
        Order.objects.select_related("customer__customer_profile", "farmer", "market")
        .prefetch_related("items", "status_history__changed_by")
        .annotate(item_count=Count("items", distinct=True)),
        message="Order not found.",
        pk=order_id,
    )
