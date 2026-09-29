from typing import Any

from django.db.models import Count, Q
from django.utils import timezone

from accounts.selectors import public_farmers
from markets.selectors import public_markets
from notifications.models import Notification
from orders.models import Order, OrderStatus
from orders.selectors import OPEN_TAB, customer_orders_queryset

UPCOMING_LIMIT = 3
FAVORITE_FARMER_LIMIT = 4
NOTIFICATION_LIMIT = 5


def _counts(customer) -> dict[str, int]:
    return Order.objects.filter(customer=customer).aggregate(
        open=Count("pk", filter=Q(status__in=OPEN_TAB)),
        ready_for_pickup=Count("pk", filter=Q(status=OrderStatus.READY_FOR_PICKUP)),
        completed=Count("pk", filter=Q(status=OrderStatus.COMPLETED)),
        pending_review=Count(
            "pk",
            filter=Q(status=OrderStatus.COMPLETED)
            & (Q(farmer_review__isnull=True) | Q(items__product_review__isnull=True)),
            distinct=True,
        ),
    )


def upcoming_orders(customer, now):
    """Open orders whose pickup has not started yet, nearest first."""
    return customer_orders_queryset(customer, tab="open", ordering="pickup_start_at").filter(
        pickup_start_at__gt=now
    )[:UPCOMING_LIMIT]


def favorite_farmers(customer):
    return public_farmers().filter(favorited_by__customer=customer)[:FAVORITE_FARMER_LIMIT]


def favorite_markets(customer):
    return public_markets().filter(favorited_by__customer=customer)


def build_customer_dashboard(*, customer) -> dict[str, Any]:
    """Every block of CU-01 except the serialization, which the view does."""
    now = timezone.now()
    last_order_id = (
        Order.objects.filter(customer=customer).order_by("-created_at", "-pk").values_list("pk", flat=True).first()
    )
    return {
        "counts": _counts(customer),
        "upcoming": upcoming_orders(customer, now),
        "favorite_farmers": favorite_farmers(customer),
        "favorite_markets": favorite_markets(customer),
        "last_order_id": last_order_id,
        "recent_notifications": Notification.objects.filter(recipient=customer).order_by(
            "-created_at", "-pk"
        )[:NOTIFICATION_LIMIT],
    }


def sweep_farmers_of(customer) -> list[int]:
    """Farmer ids whose overdue orders this customer holds, so the sweep touches only those (A-005)."""
    return list(
        Order.objects.filter(
            customer=customer, status=OrderStatus.PLACED, pickup_start_at__lte=timezone.now()
        )
        .values_list("farmer_id", flat=True)
        .distinct()
    )
