from django.db import transaction

from accounts.models import FarmerProfile, FarmerStatus
from marketlink_core.exceptions import BusinessValidationError, ErrorCode
from notifications.models import NotificationType
from notifications.services import notify
from orders.admin_selectors import open_order_breakdown
from orders.models import OPEN_STATUSES, ActorRole, Order, OrderStatus
from orders.services.fsm import transition_order

# D-015: PENDING -> APPROVED <-> SUSPENDED, and PENDING -> REJECTED.
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
    # django-simple-history fills farmer_profile_histories, which A-03 renders as the
    # approval trail: who changed the status, when, and why.
    profile._history_user = actor
    # A cascade stamps its own marker here rather than the sentence shown to the farmer, so
    # that undoing the cascade later can find exactly the rows it caused - the same trick
    # market closure already uses on pickup slots.
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
    # status_reason is cleared: the suspension it explained is over.
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


# §5.4: suspend the stall, then decline every open order and give the stock back.
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

    # Ordered by id so this never deadlocks against a farmer or customer acting on the same
    # rows. No reason is passed: for an admin transition the FSM stamps the FARMER_SUSPENDED_BY_ADMIN
    # change_reason itself (§5.4 step 5), gives back the stock of the orders that held any
    # (D-029: a PLACED order never took stock) and writes order_status_history.
    order_ids = list(
        Order.objects.filter(farmer_id=farmer_id, status__in=OPEN_STATUSES)
        .order_by("id")
        .values_list("id", flat=True)
    )
    # §5.4 step 4: a pending change request dies with the order it belonged to.
    Order.objects.filter(pk__in=order_ids).exclude(pending_change=None).update(pending_change=None)
    for order_id in order_ids:
        transition_order(
            order_id=order_id,
            to_status=OrderStatus.DECLINED,
            actor=actor,
            actor_role=ActorRole.ADMIN,
        )

    # A caller that already tells the farmer what happened turns this off, so the stall is
    # not told the same thing twice in two different words.
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
