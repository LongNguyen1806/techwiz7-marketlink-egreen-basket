"""CU-01 / C-00: the figures and shortcuts on the customer's own dashboard (FR-03, FR-32).

Read-only. The caller runs the lazy sweep first (A-005, D-009) so an overdue PLACED order is not
counted as open, then serializes each block with the schema its own branch owns.
"""

from typing import Any

from django.db.models import Count, Q
from django.utils import timezone

from accounts.selectors import public_farmers
from markets.selectors import public_markets
from notifications.models import Notification
from orders.models import Order, OrderStatus
from orders.selectors import OPEN_TAB, customer_orders_queryset

UPCOMING_LIMIT = 3  # C-00 shows the three nearest pickups
FAVORITE_FARMER_LIMIT = 4  # C-00 shows four farmer cards
NOTIFICATION_LIMIT = 5  # C-00 shows five notification rows


def _counts(customer) -> dict[str, int]:
    """One query for the four cards on C-00.

    `ready_for_pickup` is also part of `open`: C-00 repeats it as a separate reminder card.
    `pending_review` counts COMPLETED orders that still miss a review (D-016), not single reviews.
    """
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
