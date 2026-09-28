from django.db import transaction

from accounts.models import FarmerProfile, FarmerStatus
from marketlink_core.exceptions import BusinessValidationError, ErrorCode
from notifications.models import NotificationType
from notifications.services import notify
from orders.admin_selectors import open_order_breakdown
from orders.models import OPEN_STATUSES, ActorRole, Order, OrderStatus
from orders.services.fsm import transition_order

ALLOWED_FROM = {
    FarmerStatus.APPROVED: (FarmerStatus.PENDING, FarmerStatus.SUSPENDED),
    FarmerStatus.REJECTED: (FarmerStatus.PENDING,),
    FarmerStatus.SUSPENDED: (FarmerStatus.APPROVED,),
}

STATUS_LABEL = {
    FarmerStatus.APPROVED: "approved",
    FarmerStatus.REJECTED: "rejected",
    FarmerStatus.SUSPENDED: "suspended",
}


def _load_locked(farmer_id: int) -> FarmerProfile:
    return FarmerProfile.objects.select_for_update().select_related("user").get(pk=farmer_id)


def _require_transition(profile: FarmerProfile, to_status: str) -> None:
    if profile.status not in ALLOWED_FROM[to_status]:
        raise BusinessValidationError(
            f"A {profile.status.lower()} stall cannot be {STATUS_LABEL[to_status]}.",
            code=ErrorCode.INVALID_STATUS_TRANSITION,
        )


def _apply(
    profile: FarmerProfile,
    *,
    to_status: str,
    reason: str | None,
    actor,
    history_reason: str | None = None,
) -> None:
    profile.status = to_status
    profile.status_reason = reason
    profile._history_user = actor
    profile._change_reason = history_reason or reason
    profile.save(update_fields=["status", "status_reason", "updated_at"])


def _notify_status(profile: FarmerProfile, *, to_status: str, reason: str | None) -> None:
    notify(
        recipient=profile.user,
        event_type=NotificationType.ACCOUNT_STATUS_CHANGED,
        context={"status_label": STATUS_LABEL[to_status], "reason": reason or ""},
    )


@transaction.atomic
def approve_farmer(*, farmer_id: int, actor) -> FarmerProfile:
    profile = _load_locked(farmer_id)
    _require_transition(profile, FarmerStatus.APPROVED)
    _apply(profile, to_status=FarmerStatus.APPROVED, reason=None, actor=actor)
    _notify_status(profile, to_status=FarmerStatus.APPROVED, reason=None)
    return profile


@transaction.atomic
def reject_farmer(*, farmer_id: int, reason: str, actor) -> FarmerProfile:
    profile = _load_locked(farmer_id)
    _require_transition(profile, FarmerStatus.REJECTED)
    _apply(profile, to_status=FarmerStatus.REJECTED, reason=reason, actor=actor)
    _notify_status(profile, to_status=FarmerStatus.REJECTED, reason=reason)
    return profile


@transaction.atomic
def reinstate_farmer(
    *,
    farmer_id: int,
    actor,
    history_reason: str | None = None,
    send_notification: bool = True,
) -> FarmerProfile:
    profile = _load_locked(farmer_id)
    _require_transition(profile, FarmerStatus.APPROVED)
    _apply(
        profile,
        to_status=FarmerStatus.APPROVED,
        reason=None,
        actor=actor,
        history_reason=history_reason,
    )
    if send_notification:
        _notify_status(profile, to_status=FarmerStatus.APPROVED, reason=None)
    return profile


@transaction.atomic
def suspend_farmer(
    *,
    farmer_id: int,
    reason: str,
    actor,
    history_reason: str | None = None,
    send_notification: bool = True,
) -> tuple[FarmerProfile, int]:
    profile = _load_locked(farmer_id)
    _require_transition(profile, FarmerStatus.SUSPENDED)
    _apply(
        profile,
        to_status=FarmerStatus.SUSPENDED,
        reason=reason,
        actor=actor,
        history_reason=history_reason,
    )

    order_ids = list(
        Order.objects.filter(farmer_id=farmer_id, status__in=OPEN_STATUSES)
        .order_by("id")
        .values_list("id", flat=True)
    )
    Order.objects.filter(pk__in=order_ids).exclude(pending_change=None).update(pending_change=None)
    for order_id in order_ids:
        transition_order(
            order_id=order_id,
            to_status=OrderStatus.DECLINED,
            actor=actor,
            actor_role=ActorRole.ADMIN,
        )

    if send_notification:
        _notify_status(profile, to_status=FarmerStatus.SUSPENDED, reason=reason)
    return profile, len(order_ids)


def suspension_impact(*, farmer_id: int) -> dict:
    orders = Order.objects.filter(farmer_id=farmer_id)
    return {
        "open_orders": open_order_breakdown(orders),
        "affected_customers": orders.filter(status__in=OPEN_STATUSES)
        .values("customer_id")
        .distinct()
        .count(),
    }
