from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.utils import timezone

from accounts.models import FarmerStatus
from catalog.services.stock import apply_stock_delta, lock_products
from marketlink_core.context import get_request_id
from marketlink_core.exceptions import (
    BusinessValidationError,
    ConflictError,
    ErrorCode,
    ForbiddenActionError,
    PreconditionRequiredError,
    UnprocessableEntityError,
)
from notifications.models import NotificationType
from notifications.services import notify
from orders.models import ActorRole, ChangeReason, Order, OrderStatus, OrderStatusHistory, Transition
from orders.services.notification_context import build_order_context

REASON_MIN_LENGTH = 5
REASON_MAX_LENGTH = 500
NO_REASON_TEXT = "No reason given."

SYSTEM_REASON_TEXT = {
    ChangeReason.FARMER_SUSPENDED_BY_ADMIN: "The farmer's stall has been suspended by an administrator.",
    ChangeReason.CUSTOMER_LOCKED_BY_ADMIN: "The customer's account has been locked by an administrator.",
    ChangeReason.PRODUCT_BLOCKED_BY_ADMIN: "An item in this order was removed by an administrator.",
    ChangeReason.SYSTEM_EXPIRED: "The order was not confirmed before the pickup time.",
}


@dataclass(frozen=True)
class TransitionRule:
    code: str
    actors: frozenset[str]
    restores_stock: bool = False


_S = OrderStatus
_R = ActorRole

# Placed orders hold virtual reservation; physical stock is deducted upon ACCEPTED (T2).
# Therefore, cancellations from PLACED (T3, T5, T8) do not restore physical stock.
TRANSITIONS: dict[tuple[str | None, str], TransitionRule] = {
    (None, _S.PLACED): TransitionRule(Transition.T1, frozenset({_R.CUSTOMER})),
    (_S.PLACED, _S.ACCEPTED): TransitionRule(Transition.T2, frozenset({_R.FARMER})),
    (_S.PLACED, _S.DECLINED): TransitionRule(Transition.T3, frozenset({_R.FARMER, _R.ADMIN}), False),
    (_S.ACCEPTED, _S.DECLINED): TransitionRule(Transition.T4, frozenset({_R.FARMER, _R.ADMIN}), True),
    (_S.PLACED, _S.CANCELLED): TransitionRule(Transition.T5, frozenset({_R.CUSTOMER, _R.ADMIN}), False),
    (_S.ACCEPTED, _S.CANCELLED): TransitionRule(Transition.T6, frozenset({_R.CUSTOMER, _R.ADMIN}), True),
    (_S.PLACED, _S.EXPIRED): TransitionRule(Transition.T8, frozenset({_R.SYSTEM}), False),
    (_S.ACCEPTED, _S.READY_FOR_PICKUP): TransitionRule(Transition.T9, frozenset({_R.FARMER})),
    (_S.READY_FOR_PICKUP, _S.COMPLETED): TransitionRule(Transition.T10, frozenset({_R.FARMER})),
    (_S.READY_FOR_PICKUP, _S.NO_SHOW): TransitionRule(Transition.T11, frozenset({_R.FARMER}), True),
    (_S.READY_FOR_PICKUP, _S.DECLINED): TransitionRule(Transition.T12, frozenset({_R.ADMIN}), True),
    (_S.READY_FOR_PICKUP, _S.CANCELLED): TransitionRule(Transition.T13, frozenset({_R.ADMIN}), True),
    (_S.ACCEPTED, _S.NO_SHOW): TransitionRule(Transition.T14, frozenset({_R.FARMER}), True),
}


def transition_order(
    *,
    order_id: int,
    to_status: str,
    actor: Any | None,
    actor_role: str,
    expected_version: int | None = None,
    reason: str | None = None,
    admin_change_reason: str | None = None,
) -> Order:
    reason = (reason or "").strip() or None
    with transaction.atomic():
        order = (
            Order.objects.select_for_update(of=("self",))
            .select_related("farmer__user", "market", "customer__customer_profile")
            .get(id=order_id)
        )
        _check_version(order, actor_role, expected_version)
        rule = TRANSITIONS.get((order.status, to_status))
        if rule is None:
            raise BusinessValidationError(
                f"This order cannot change from {order.status} to {to_status}.",
                code=ErrorCode.INVALID_STATUS_TRANSITION,
            )
        _check_actor(order, rule, actor, actor_role)
        change_reason = _check_preconditions(
            order, rule, actor_role, reason, admin_change_reason
        )

        # Locking order: orders (already locked above) -> products (sorted by id)
        if rule.code == Transition.T2:
            _deduct_stock(order)
        elif rule.restores_stock:
            _restore_stock(order)

        from_status = order.status
        order.status = to_status
        order.version += 1
        order.save(update_fields=["status", "version", "updated_at"])
        OrderStatusHistory.objects.create(
            order=order,
            from_status=from_status,
            to_status=to_status,
            transition=rule.code,
            actor=None if actor_role == _R.SYSTEM else actor,
            actor_role=actor_role,
            change_reason=change_reason,
            request_id=get_request_id(),
        )
        _send_notifications(order, rule, actor_role, change_reason)
    return order


def record_order_placed(*, order: Order, actor: Any) -> None:
    OrderStatusHistory.objects.create(
        order=order,
        from_status=None,
        to_status=_S.PLACED,
        transition=Transition.T1,
        actor=actor,
        actor_role=_R.CUSTOMER,
        request_id=get_request_id(),
    )
    notify(
        recipient=order.farmer.user,
        event_type=NotificationType.ORDER_PLACED,
        context=build_order_context(order),
    )


def _check_version(order: Order, actor_role: str, expected_version: int | None) -> None:
    if expected_version is None:
        if actor_role in (_R.CUSTOMER, _R.FARMER):
            raise PreconditionRequiredError("The If-Match header is required.")
        return
    if order.version != expected_version:
        raise ConflictError(
            "This order was just updated by someone else. Please reload.",
            code=ErrorCode.RESOURCE_MODIFIED,
        )


def _check_actor(order: Order, rule: TransitionRule, actor: Any | None, actor_role: str) -> None:
    if actor_role not in rule.actors:
        raise ForbiddenActionError(code=ErrorCode.ACTION_NOT_PERMITTED_FOR_ROLE)
    if actor_role == _R.FARMER:
        if order.farmer_id != getattr(actor, "pk", None):
            raise ForbiddenActionError(code=ErrorCode.ACTION_NOT_PERMITTED_FOR_ROLE)
        if order.farmer.status == FarmerStatus.SUSPENDED:
            raise ForbiddenActionError(
                "Your stall is suspended, so orders cannot be updated.",
                code=ErrorCode.FARMER_SUSPENDED,
            )
    elif actor_role == _R.CUSTOMER and order.customer_id != getattr(actor, "pk", None):
        raise ForbiddenActionError(code=ErrorCode.ACTION_NOT_PERMITTED_FOR_ROLE)


def _check_preconditions(
    order: Order,
    rule: TransitionRule,
    actor_role: str,
    reason: str | None,
    admin_change_reason: str | None = None,
) -> str | None:
    if reason and len(reason) > REASON_MAX_LENGTH:
        raise BusinessValidationError(
            errors={"reason": [f"Reason must be at most {REASON_MAX_LENGTH} characters."]}
        )
    now = timezone.now()
    code = rule.code

    if actor_role == _R.FARMER:
        if code in (Transition.T2, Transition.T3, Transition.T4) and now >= order.pickup_start_at:
            raise UnprocessableEntityError(
                "The pickup time has already started.", code=ErrorCode.PICKUP_ALREADY_STARTED
            )
        if code == Transition.T9:
            if order.pending_change:
                raise UnprocessableEntityError(
                    "Cannot mark ready while a change request is pending.",
                    code=ErrorCode.FAILED_PRECONDITION,
                )
            if now < order.cutoff_at:
                raise UnprocessableEntityError(
                    "The order can be marked ready only after the cutoff time.",
                    code=ErrorCode.CUTOFF_NOT_REACHED,
                )
        if code in (Transition.T11, Transition.T14) and now < order.pickup_end_at:
            raise UnprocessableEntityError(
                "A no-show can be recorded only after the pickup window ends.",
                code=ErrorCode.PICKUP_NOT_ENDED,
            )
        if code in (Transition.T3, Transition.T4):
            if not reason or len(reason) < REASON_MIN_LENGTH:
                raise BusinessValidationError(
                    errors={"reason": [f"Please enter a reason ({REASON_MIN_LENGTH}–{REASON_MAX_LENGTH} characters)."]}
                )
        return reason

    if actor_role == _R.CUSTOMER:
        if code in (Transition.T5, Transition.T6) and now >= order.cutoff_at:
            raise UnprocessableEntityError(
                "The cutoff time for changing this order has passed.", code=ErrorCode.CUTOFF_PASSED
            )
        return reason

    if actor_role == _R.ADMIN:
        # Fixed system reason prevents leaking internal administrative notes into end-user emails.
        # The caller may name which fixed reason applies, because the same DECLINED transitions
        # now serve two different admin actions: suspending a stall and blocking one product.
        # Without this, a shopper whose order died because of a takedown would be told the
        # stall had been suspended, which is simply untrue.
        if admin_change_reason:
            return admin_change_reason
        if code in (Transition.T3, Transition.T4, Transition.T12):
            return ChangeReason.FARMER_SUSPENDED_BY_ADMIN
        return ChangeReason.CUSTOMER_LOCKED_BY_ADMIN

    if code == Transition.T8:
        if now < order.pickup_start_at:
            raise UnprocessableEntityError(code=ErrorCode.FAILED_PRECONDITION)
        return ChangeReason.SYSTEM_EXPIRED
    return reason


def _deduct_stock(order: Order) -> None:
    deltas: dict[int, int] = {}
    for item in order.items.all():
        deltas[item.product_id] = deltas.get(item.product_id, 0) - item.quantity
    if deltas:
        apply_stock_delta(products=lock_products(product_ids=deltas.keys()), deltas=deltas)


def _restore_stock(order: Order) -> None:
    deltas: dict[int, int] = {}
    for item in order.items.all():
        deltas[item.product_id] = deltas.get(item.product_id, 0) + item.quantity
    if deltas:
        apply_stock_delta(products=lock_products(product_ids=deltas.keys()), deltas=deltas)


def _send_notifications(
    order: Order, rule: TransitionRule, actor_role: str, change_reason: str | None
) -> None:
    context = build_order_context(order)
    readable_reason = SYSTEM_REASON_TEXT.get(change_reason, change_reason) or NO_REASON_TEXT
    customer, farmer_user = order.customer, order.farmer.user
    code = rule.code

    if code == Transition.T2:
        notify(recipient=customer, event_type=NotificationType.ORDER_ACCEPTED, context=context)
    elif code in (Transition.T3, Transition.T4, Transition.T12):
        notify(
            recipient=customer,
            event_type=NotificationType.ORDER_DECLINED,
            context={**context, "reason": readable_reason},
        )
    elif code in (Transition.T5, Transition.T6, Transition.T13):
        if actor_role == _R.ADMIN:
            notify(
                recipient=farmer_user,
                event_type=NotificationType.ORDER_CANCELLED_CUSTOMER_LOCKED,
                context=context,
            )
        else:
            notify(
                recipient=farmer_user,
                event_type=NotificationType.ORDER_CANCELLED,
                context={**context, "reason": readable_reason},
            )
    elif code == Transition.T8:
        notify(recipient=customer, event_type=NotificationType.ORDER_EXPIRED, context=context)
    elif code == Transition.T9:
        notify(recipient=customer, event_type=NotificationType.ORDER_READY, context=context)
