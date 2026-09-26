from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any, TypeVar

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
    ResourceNotFoundError,
    UnprocessableEntityError,
)
from marketlink_core.history import save_with_history
from marketlink_core.services.db_retry import run_with_deadlock_retry
from notifications.models import NotificationType
from notifications.services import notify
from orders.models import ActorRole, ChangeReason, Order, OrderStatus, OrderStatusHistory, Transition
from orders.services.notification_context import build_order_context

REASON_MIN_LENGTH = 5
REASON_MAX_LENGTH = 500
NO_REASON_TEXT = "No reason given."

T = TypeVar("T")

# ORDER_CANCELLED_CUSTOMER_LOCKED: tell the farmer what happened to stock (D-015, D-029).
LOCKED_STOCK_RETURNED_NOTE = "The items have been returned to your online stock."
LOCKED_STOCK_UNCHANGED_NOTE = "The order had not been accepted yet, so your stock did not change."

SYSTEM_REASON_TEXT = {
    ChangeReason.FARMER_SUSPENDED_BY_ADMIN: "The farmer's stall has been suspended by an administrator.",
    ChangeReason.CUSTOMER_LOCKED_BY_ADMIN: "The customer's account has been locked by an administrator.",
    ChangeReason.MARKET_CLOSED_BY_ADMIN: "The market has been closed by an administrator.",
    ChangeReason.SYSTEM_EXPIRED: "The order was not confirmed before the pickup time.",
}

# Admin never types a reason into an order (D-033): each admin cascade stamps a fixed system
# code. The first code of each group is the default, so AD-07 / AD-12 need not pass one.
ADMIN_DECLINE_REASONS = (ChangeReason.FARMER_SUSPENDED_BY_ADMIN, ChangeReason.MARKET_CLOSED_BY_ADMIN)
ADMIN_CANCEL_REASONS = (ChangeReason.CUSTOMER_LOCKED_BY_ADMIN,)


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


def run_with_retry_if_top_level(fn: Callable[[], T]) -> T:
    """Retry deadlocks only when fn owns the whole transaction.

    InnoDB rolls back the entire transaction on a deadlock, so retrying inside an outer
    atomic block would reuse a broken transaction. Callers that already hold a transaction
    (e.g. admin cascades) must retry at their own top level.
    """
    if transaction.get_connection().in_atomic_block:
        return fn()
    return run_with_deadlock_retry(fn)


def transition_order(
    *,
    order_id: int,
    to_status: str,
    actor: Any | None,
    actor_role: str,
    expected_version: int | None = None,
    reason: str | None = None,
    sold_out_product_ids: Iterable[int] | None = None,
    mark_all_sold_out: bool = False,
    admin_reason: str | None = None,
    notify_customer: bool = True,
) -> Order:
    """Apply one FSM edge under row locks (orders -> products).

    sold_out_product_ids / mark_all_sold_out only apply to farmer declines (T3, T4).
    ``None`` means the farmer did not declare sold-out items; an empty list means
    "no item is sold out". T4 by a farmer requires a declaration.

    admin_reason / notify_customer are for admin cascades only. admin_reason picks the
    system code stamped on the order (ADMIN_DECLINE_REASONS / ADMIN_CANCEL_REASONS; the
    default is the first of each). notify_customer=False lets a caller that sends its own
    summary (AD-17 market closure) skip the per-order customer notification.
    """
    if actor_role != _R.ADMIN and (admin_reason is not None or not notify_customer):
        raise ValueError("admin_reason and notify_customer are only for admin transitions.")
    reason = (reason or "").strip() or None
    sold_out_ids = None if sold_out_product_ids is None else set(sold_out_product_ids)

    def _execute() -> Order:
        with transaction.atomic():
            order = (
                Order.objects.select_for_update(of=("self",))
                .select_related("farmer__user", "market", "customer__customer_profile")
                .filter(id=order_id)
                .first()
            )
            if order is None:
                raise ResourceNotFoundError("Order not found.", code=ErrorCode.NOT_FOUND)
            # Ownership first so an order outside the actor's scope never reveals its state.
            _check_ownership(order, actor, actor_role)
            rule = TRANSITIONS.get((order.status, to_status))
            if rule is None:
                raise BusinessValidationError(
                    f"This order cannot change from {order.status} to {to_status}.",
                    code=ErrorCode.INVALID_STATUS_TRANSITION,
                )
            _check_role(rule, actor_role)
            _check_version(order, actor_role, expected_version)
            change_reason = _check_preconditions(order, rule, actor_role, reason, admin_reason)
            sold_out_targets = _resolve_sold_out_targets(
                order, rule, actor_role, sold_out_ids, mark_all_sold_out
            )

            # Audit trail (v1.8): every history row of this action names the order and the edge;
            # system actions (lazy sweep) are recorded without a user.
            history_user = None if actor_role == _R.SYSTEM else actor
            history_reason = f"Order #{order.pk}: {order.status} -> {to_status} ({rule.code})"

            # Locking order: orders (already locked above) -> products (sorted by id)
            if rule.code == Transition.T2:
                _deduct_stock(order, reason=history_reason, user=history_user)
            elif rule.restores_stock:
                _restore_stock(order, reason=history_reason, user=history_user)
            if sold_out_targets:
                _mark_products_sold_out(
                    sold_out_targets, reason=f"{history_reason}: declared sold out", user=history_user
                )

            from_status = order.status
            order.status = to_status
            order.version += 1
            update_fields = ["status", "version", "updated_at"]
            if to_status in (_S.DECLINED, _S.CANCELLED, _S.NO_SHOW, _S.COMPLETED, _S.EXPIRED):
                if order.pending_change is not None:
                    order.pending_change = None
                    update_fields.append("pending_change")
            save_with_history(order, update_fields=update_fields, reason=history_reason, user=history_user)
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
            _send_notifications(order, rule, actor_role, change_reason, notify_customer=notify_customer)
        return order

    return run_with_retry_if_top_level(_execute)


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


def _check_ownership(order: Order, actor: Any | None, actor_role: str) -> None:
    if actor_role == _R.FARMER:
        if order.farmer_id != getattr(actor, "pk", None):
            raise ResourceNotFoundError("Order not found.", code=ErrorCode.NOT_FOUND)
        if order.farmer.status == FarmerStatus.SUSPENDED:
            raise ForbiddenActionError(
                "Your stall is suspended, so orders cannot be updated.",
                code=ErrorCode.FARMER_SUSPENDED,
            )
    elif actor_role == _R.CUSTOMER:
        if order.customer_id != getattr(actor, "pk", None):
            raise ResourceNotFoundError("Order not found.", code=ErrorCode.NOT_FOUND)


def _check_role(rule: TransitionRule, actor_role: str) -> None:
    if actor_role not in rule.actors:
        raise ForbiddenActionError(code=ErrorCode.ACTION_NOT_PERMITTED_FOR_ROLE)


def _resolve_sold_out_targets(
    order: Order,
    rule: TransitionRule,
    actor_role: str,
    sold_out_ids: set[int] | None,
    mark_all_sold_out: bool,
) -> set[int]:
    declared = mark_all_sold_out or sold_out_ids is not None
    is_farmer_decline = actor_role == _R.FARMER and rule.code in (Transition.T3, Transition.T4)
    if not is_farmer_decline:
        if declared and (mark_all_sold_out or sold_out_ids):
            raise BusinessValidationError(
                "Items can be marked sold out only when the farmer declines an order.",
                errors={"mark_sold_out_product_ids": ["Not allowed for this action."]},
            )
        return set()

    # T4 returns stock, so the farmer must say explicitly which items are gone (W1.2).
    if rule.code == Transition.T4 and not declared:
        raise BusinessValidationError(
            "Please state which items are sold out before declining an accepted order.",
            errors={
                "mark_sold_out_product_ids": [
                    "Required for accepted orders. Send an empty list to return every item to stock."
                ]
            },
        )

    order_product_ids = {item.product_id for item in order.items.all()}
    if mark_all_sold_out:
        return order_product_ids
    targets = sold_out_ids or set()
    unknown = targets - order_product_ids
    if unknown:
        raise BusinessValidationError(
            "Sold-out items must be items of this order.",
            errors={
                "mark_sold_out_product_ids": [
                    f"Product IDs {sorted(unknown)} are not part of this order."
                ]
            },
        )
    return targets


def _admin_change_reason(code: str, admin_reason: str | None) -> str:
    allowed = (
        ADMIN_DECLINE_REASONS
        if code in (Transition.T3, Transition.T4, Transition.T12)
        else ADMIN_CANCEL_REASONS
    )
    if admin_reason is None:
        return allowed[0]
    if admin_reason not in allowed:
        raise ValueError(f"{admin_reason!r} is not a valid admin reason for {code}.")
    return admin_reason


def _check_preconditions(
    order: Order,
    rule: TransitionRule,
    actor_role: str,
    reason: str | None,
    admin_reason: str | None = None,
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
        return _admin_change_reason(code, admin_reason)

    if code == Transition.T8:
        if now < order.pickup_start_at:
            raise UnprocessableEntityError(code=ErrorCode.FAILED_PRECONDITION)
        return ChangeReason.SYSTEM_EXPIRED
    return reason


def _deduct_stock(order: Order, *, reason: str, user: Any) -> None:
    deltas: dict[int, int] = {}
    for item in order.items.all():
        deltas[item.product_id] = deltas.get(item.product_id, 0) - item.quantity
    if deltas:
        apply_stock_delta(
            products=lock_products(product_ids=deltas.keys()), deltas=deltas, reason=reason, user=user
        )


def _restore_stock(order: Order, *, reason: str, user: Any) -> None:
    deltas: dict[int, int] = {}
    for item in order.items.all():
        deltas[item.product_id] = deltas.get(item.product_id, 0) + item.quantity
    if deltas:
        apply_stock_delta(
            products=lock_products(product_ids=deltas.keys()), deltas=deltas, reason=reason, user=user
        )


def _mark_products_sold_out(product_ids: set[int], *, reason: str, user: Any) -> None:
    # Runs after any T4 restock so the final stock of these products is exactly 0.
    for product in lock_products(product_ids=product_ids).values():
        if product.stock_quantity != 0:
            product.stock_quantity = 0
            save_with_history(product, update_fields=["stock_quantity", "updated_at"], reason=reason, user=user)


def _send_notifications(
    order: Order,
    rule: TransitionRule,
    actor_role: str,
    change_reason: str | None,
    *,
    notify_customer: bool = True,
) -> None:
    context = build_order_context(order)
    readable_reason = SYSTEM_REASON_TEXT.get(change_reason, change_reason) or NO_REASON_TEXT
    customer, farmer_user = order.customer, order.farmer.user
    code = rule.code

    if not notify_customer and code in (Transition.T3, Transition.T4, Transition.T12):
        # The caller tells the customer itself (AD-17 sends one MARKET_CLOSED per customer).
        return
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
                context={
                    **context,
                    "stock_note": (
                        LOCKED_STOCK_RETURNED_NOTE
                        if rule.restores_stock
                        else LOCKED_STOCK_UNCHANGED_NOTE
                    ),
                },
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
