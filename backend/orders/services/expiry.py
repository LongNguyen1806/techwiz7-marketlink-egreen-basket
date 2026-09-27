import logging

from django.db import transaction
from django.utils import timezone

from marketlink_core.context import get_request_id
from marketlink_core.exceptions import BusinessValidationError, ErrorCode
from marketlink_core.history import save_with_history
from notifications.models import NotificationType
from notifications.services import notify
from orders.models import ActorRole, Order, OrderStatus, OrderStatusHistory
from orders.services.fsm import run_with_retry_if_top_level, transition_order
from orders.services.notification_context import build_order_context

logger = logging.getLogger("marketlink")

CHANGE_EXPIRED_REASON = "The farmer did not respond before the pickup time."


def _in_caller_transaction() -> bool:
    return transaction.get_connection().in_atomic_block


def _handle_order_failure(order_id: int, task: str) -> None:
    """A failure on one order must not break the request that triggered the sweep (W3.2).

    Inside the caller's own transaction the connection is unusable after a database error,
    so the error is re-raised there instead of being swallowed.
    """
    if _in_caller_transaction():
        raise
    logger.exception("Lazy sweep failed to %s for order %s", task, order_id)


def _expire_change_request(order_id: int) -> bool:
    def _execute() -> bool:
        with transaction.atomic():
            order = (
                Order.objects.select_for_update(of=("self",))
                .select_related("farmer", "market", "customer__customer_profile")
                .filter(id=order_id)
                .first()
            )
            if (
                order is None
                or order.status != OrderStatus.ACCEPTED
                or not order.pending_change
                or order.pickup_start_at > timezone.now()
            ):
                return False
            order.pending_change = None
            order.version += 1
            save_with_history(
                order,
                update_fields=["pending_change", "version", "updated_at"],
                reason=f"Order #{order.pk}: change request expired",
                user=None,  # system action (lazy sweep)
            )

            OrderStatusHistory.objects.create(
                order=order,
                from_status=OrderStatus.ACCEPTED,
                to_status=OrderStatus.ACCEPTED,
                transition=None,
                actor=None,
                actor_role=ActorRole.SYSTEM,
                change_reason="Change request expired",
                request_id=get_request_id(),
            )
            notify(
                recipient=order.customer,
                event_type=NotificationType.ORDER_CHANGE_REJECTED,
                context={**build_order_context(order), "reason": CHANGE_EXPIRED_REASON},
            )
        return True

    return run_with_retry_if_top_level(_execute)


def expire_overdue_orders(*, farmer_id: int | None = None) -> int:
    """A-005 lazy sweep. Each order runs in its own transaction; returns the number expired."""
    now = timezone.now()

    # 1. Expire PLACED orders whose pickup has started (A-005, D-029: stock unchanged)
    overdue_placed = Order.objects.filter(status=OrderStatus.PLACED, pickup_start_at__lte=now)
    if farmer_id is not None:
        overdue_placed = overdue_placed.filter(farmer_id=farmer_id)

    expired = 0
    for order_id in list(overdue_placed.order_by("id").values_list("id", flat=True)):
        try:
            transition_order(
                order_id=order_id,
                to_status=OrderStatus.EXPIRED,
                actor=None,
                actor_role=ActorRole.SYSTEM,
            )
        except BusinessValidationError as exc:
            # Someone else moved the order (e.g. the farmer accepted it) between the scan and the lock.
            if exc.code != ErrorCode.INVALID_STATUS_TRANSITION:
                _handle_order_failure(order_id, "expire")
            continue
        except Exception:  # noqa: BLE001 - one broken order must not block the others (W3.2)
            _handle_order_failure(order_id, "expire")
            continue
        expired += 1

    # 2. Drop change requests of ACCEPTED orders whose pickup has started (D-030, CT-21)
    overdue_changes = Order.objects.filter(
        status=OrderStatus.ACCEPTED,
        pickup_start_at__lte=now,
        pending_change__isnull=False,
    )
    if farmer_id is not None:
        overdue_changes = overdue_changes.filter(farmer_id=farmer_id)

    for order_id in list(overdue_changes.order_by("id").values_list("id", flat=True)):
        try:
            _expire_change_request(order_id)
        except Exception:  # noqa: BLE001 - see W3.2 above
            _handle_order_failure(order_id, "expire the change request")

    return expired
