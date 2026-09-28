"""A shopper who fails to collect three orders within the at-risk window is locked automatically.

The threshold and the window are the at-risk ones the admin list already shows (3 in 30 days),
so "at risk" and "locked" are the same count. Only no-shows after the account was last unlocked
count: an admin who unlocks someone gives them a fresh start, or the next no-show would lock
them again straight away on the old three.
"""

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Max

from accounts.services.customer_status_service import deactivate_customer
from notifications.models import NotificationType
from notifications.services import notify
from orders.admin_selectors import at_risk_threshold, at_risk_window_days, at_risk_window_start
from orders.models import Order, OrderStatus, OrderStatusHistory
from system.models import AuditAction, AuditLog
from system.services import log_security_event

AUTO_LOCK_PREFIX = "Auto-locked"


def _counting_since(customer_id: int):
    since = at_risk_window_start()
    last_unlock = AuditLog.objects.filter(
        action=AuditAction.CUSTOMER_ACTIVATED, details__customer_id=customer_id
    ).aggregate(at=Max("created_at"))["at"]
    return max(since, last_unlock) if last_unlock else since


def recent_no_show_orders(customer_id: int) -> list[Order]:
    """The no-shows that count toward a lock, newest first."""
    rows = (
        OrderStatusHistory.objects.filter(
            order__customer_id=customer_id,
            to_status=OrderStatus.NO_SHOW,
            created_at__gte=_counting_since(customer_id),
        )
        .order_by("-created_at")
        .values_list("order_id", flat=True)
    )
    ids = list(dict.fromkeys(rows))
    orders = Order.objects.select_related("farmer", "market").in_bulk(ids)
    return [orders[i] for i in ids if i in orders]


def lock_if_repeated_no_shows(customer_id: int) -> bool:
    """Lock the account when the no-shows reach the threshold. Returns whether it locked."""
    user = get_user_model().objects.filter(pk=customer_id, is_active=True).first()
    if user is None or not hasattr(user, "customer_profile"):
        return False
    orders = recent_no_show_orders(customer_id)
    threshold = at_risk_threshold()
    if len(orders) < threshold:
        return False

    counted = orders[:threshold]
    numbers = ", ".join(f"#{order.pk}" for order in reversed(counted))
    reason = (
        f"{AUTO_LOCK_PREFIX}: did not collect orders {numbers} "
        f"within {at_risk_window_days()} days."
    )
    with transaction.atomic():
        _, cancelled = deactivate_customer(customer_id=customer_id, reason=reason, actor=None)
        log_security_event(
            action=AuditAction.CUSTOMER_AUTO_LOCKED,
            user=None,
            endpoint=None,
            method=None,
            ip_address=None,
            user_agent=None,
            status_code=None,
            request_id=None,
            details={
                "customer_id": customer_id,
                "no_show_order_ids": [order.pk for order in reversed(counted)],
                "cancelled_open_orders": cancelled,
            },
        )
        notify(
            recipient=user,
            event_type=NotificationType.ACCOUNT_LOCKED_NO_SHOW,
            context={"order_numbers": numbers, "count": threshold},
        )
    return True


def auto_lock_summary(customer_id: int) -> dict | None:
    """What the admin's customer page shows about an automatic lock, if the account has one."""
    user = get_user_model().objects.filter(pk=customer_id).first()
    if user is None or user.is_active:
        return None
    entry = (
        AuditLog.objects.filter(
            action=AuditAction.CUSTOMER_AUTO_LOCKED, details__customer_id=customer_id
        )
        .order_by("-created_at")
        .first()
    )
    if entry is None:
        return None
    # A later manual lock replaces the automatic one as the reason for the account being off.
    manual_after = AuditLog.objects.filter(
        action=AuditAction.CUSTOMER_DEACTIVATED,
        details__customer_id=customer_id,
        created_at__gt=entry.created_at,
    ).exists()
    if manual_after:
        return None
    ids = entry.details.get("no_show_order_ids", [])
    orders = Order.objects.select_related("farmer", "market").in_bulk(ids)
    return {
        "locked_at": entry.created_at,
        "orders": [
            {
                "id": order.pk,
                "stall_name": order.farmer.stall_name,
                "market_name": order.market.name,
                "pickup_date": order.pickup_date,
                "total_amount": order.total_amount,
            }
            for order in (orders.get(i) for i in ids)
            if order is not None
        ],
    }
