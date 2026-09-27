from django.contrib.auth import get_user_model
from django.db import transaction

from accounts.models import CustomerProfile
from marketlink_core.exceptions import BusinessValidationError, ErrorCode
from notifications.services import disconnect_realtime
from orders.admin_selectors import open_order_breakdown
from orders.models import OPEN_STATUSES, ActorRole, Order, OrderStatus
from orders.services.fsm import transition_order


def _load_locked(customer_id: int):
    return (
        get_user_model()
        .objects.select_for_update(of=("self",))
        .select_related("customer_profile")
        .get(pk=customer_id)
    )


def _set_reason(user, reason: str | None) -> None:
    # D-024: the reason is required when locking and cleared when unlocking; the lock and
    # unlock history itself stays in audit_logs.
    profile = getattr(user, "customer_profile", None)
    if profile is None:
        return
    profile.deactivation_reason = reason
    profile.save(update_fields=["deactivation_reason", "updated_at"])


@transaction.atomic
def deactivate_customer(*, customer_id: int, reason: str, actor) -> tuple[object, int]:
    # §5.4: lock the account, then cancel every open order and give the stock back.
    user = _load_locked(customer_id)
    if not user.is_active:
        raise BusinessValidationError(
            "This account is already locked.", code=ErrorCode.INVALID_STATUS_TRANSITION
        )
    user.is_active = False
    user.save(update_fields=["is_active", "updated_at"])
    _set_reason(user, reason)
    # Every device of the locked account stops receiving notifications (after the commit).
    disconnect_realtime(user_id=user.pk)

    # Ordered by id to stay deadlock-free. No reason is passed: for an admin transition the FSM
    # stamps CUSTOMER_LOCKED_BY_ADMIN itself (§5.4 step 5) and gives back the stock of the orders
    # that held any (D-029: a PLACED order never took stock).
    order_ids = list(
        Order.objects.filter(customer_id=customer_id, status__in=OPEN_STATUSES)
        .order_by("id")
        .values_list("id", flat=True)
    )
    # §5.4 step 4: a pending change request dies with the order it belonged to.
    Order.objects.filter(pk__in=order_ids).exclude(pending_change=None).update(pending_change=None)
    for order_id in order_ids:
        transition_order(
            order_id=order_id,
            to_status=OrderStatus.CANCELLED,
            actor=actor,
            actor_role=ActorRole.ADMIN,
        )
    return user, len(order_ids)


@transaction.atomic
def activate_customer(*, customer_id: int) -> object:
    user = _load_locked(customer_id)
    if user.is_active:
        raise BusinessValidationError(
            "This account is already active.", code=ErrorCode.INVALID_STATUS_TRANSITION
        )
    user.is_active = True
    user.save(update_fields=["is_active", "updated_at"])
    _set_reason(user, None)
    return user


def deactivation_impact(*, customer_id: int) -> dict:
    orders = Order.objects.filter(customer_id=customer_id)
    return {
        "open_orders": open_order_breakdown(orders),
        "affected_farmers": orders.filter(status__in=OPEN_STATUSES)
        .values("farmer_id")
        .distinct()
        .count(),
    }


def customer_exists(*, customer_id: int) -> bool:
    return CustomerProfile.objects.filter(user_id=customer_id).exists()
