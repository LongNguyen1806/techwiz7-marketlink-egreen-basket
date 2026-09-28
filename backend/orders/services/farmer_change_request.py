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
    ResourceNotFoundError,
    UnprocessableEntityError,
)
from marketlink_core.history import delete_with_history, save_with_history
from markets.services.validation import validate_pickup_date
from notifications.models import NotificationType
from notifications.services import notify
from orders.models import ActorRole, Order, OrderItem, OrderStatus, OrderStatusHistory
from orders.services.fsm import run_with_retry_if_top_level
from orders.services.notification_context import build_order_context
from orders.services.pending_change import parse_pending_change

REASON_MAX_LENGTH = 500


def _lock_farmer_order(*, order_id: int, farmer_id: int, expected_version: int, verb: str) -> Order:
    """Lock the order row only (of=self) and run the shared FA-34 / FA-35 gates."""
    order = (
        Order.objects.select_for_update(of=("self",))
        .select_related("farmer__user", "market", "customer__customer_profile")
        .filter(id=order_id)
        .first()
    )
    # Ownership before anything else: an order outside the farmer's scope is simply not found.
    if order is None or order.farmer_id != farmer_id:
        raise ResourceNotFoundError("Order not found.", code=ErrorCode.NOT_FOUND)
    if order.farmer.status == FarmerStatus.SUSPENDED:
        raise ForbiddenActionError(
            f"Your stall is suspended, so change requests cannot be {verb}.",
            code=ErrorCode.FARMER_SUSPENDED,
        )
    if order.version != expected_version:
        raise ConflictError(
            "This order was just updated by someone else. Please reload.",
            code=ErrorCode.RESOURCE_MODIFIED,
        )
    if order.status != OrderStatus.ACCEPTED or not order.pending_change:
        raise UnprocessableEntityError(
            "Order is not in ACCEPTED state with a pending change request.",
            code=ErrorCode.FAILED_PRECONDITION,
        )
    if timezone.now() >= order.pickup_start_at:
        raise UnprocessableEntityError(
            "Pickup has already started for this order.",
            code=ErrorCode.PICKUP_ALREADY_STARTED,
        )
    return order


def approve_change_request(
    *,
    order_id: int,
    farmer_id: int,
    expected_version: int | None,
    actor: Any | None = None,
) -> Order:
    """FA-34: apply the customer's change request (D-030).

    Lock order: orders -> order_items -> products (old ∪ new, sorted by id).
    """
    if expected_version is None:
        raise PreconditionRequiredError("The If-Match header is required.")

    def _execute() -> Order:
        with transaction.atomic():
            order = _lock_farmer_order(
                order_id=order_id, farmer_id=farmer_id, expected_version=expected_version, verb="approved"
            )
            change = parse_pending_change(order.pending_change)
            history_reason = f"Order #{order.pk}: change request approved"

            schedule = None
            if change.pickup_date is not None:
                schedule = validate_pickup_date(
                    farmer_id=order.farmer_id,
                    market_id=order.market_id,
                    pickup_date=change.pickup_date,
                    pickup_slot_id=change.pickup_slot_id,
                )

            update_fields = ["pending_change", "version", "updated_at"]
            if change.items is not None:
                old_items = {item.product_id: item for item in order.items.select_for_update().order_by("id")}
                new_quantities = {item.product_id: item.quantity for item in change.items}
                all_product_ids = sorted(set(old_items) | set(new_quantities))
                locked_products = lock_products(product_ids=all_product_ids)

                for product_id, new_qty in new_quantities.items():
                    product = locked_products.get(product_id)
                    if product is None or product.farmer_id != order.farmer_id:
                        raise UnprocessableEntityError(
                            f"Product {product_id} does not belong to this farmer.",
                            code=ErrorCode.PRODUCT_NOT_AVAILABLE,
                        )
                    old_qty = old_items[product_id].quantity if product_id in old_items else 0
                    # max_per_order is not re-checked here: the stall itself is approving the change.
                    if new_qty > old_qty and not product.is_on_sale:
                        raise UnprocessableEntityError(
                            f"Product {product.name} is not available.",
                            code=ErrorCode.PRODUCT_NOT_AVAILABLE,
                        )

                # Positive delta returns stock, negative delta takes it (D-030).
                deltas = {}
                for product_id in all_product_ids:
                    old_qty = old_items[product_id].quantity if product_id in old_items else 0
                    delta = old_qty - new_quantities.get(product_id, 0)
                    if delta:
                        deltas[product_id] = delta
                if deltas:
                    apply_stock_delta(products=locked_products, deltas=deltas, reason=history_reason)

                # Prices come from the request: the price the customer saw (decision A, v1.8).
                # One save / delete per row (never bulk_create or queryset delete) so the audit
                # trail keeps the items as they were before the change (v1.8).
                for old_item in old_items.values():
                    delete_with_history(old_item, reason=history_reason)
                new_order_items = [
                    OrderItem(
                        order=order,
                        product=locked_products[item.product_id],
                        product_name=locked_products[item.product_id].name,
                        unit=locked_products[item.product_id].unit,
                        unit_price=item.unit_price,
                        quantity=item.quantity,
                        line_total=item.unit_price * item.quantity,
                    )
                    for item in change.items
                ]
                for new_item in new_order_items:
                    save_with_history(new_item, reason=history_reason)
                order.total_amount = sum(item.line_total for item in new_order_items)
                update_fields.append("total_amount")

            if schedule is not None:
                order.pickup_date = change.pickup_date
                order.pickup_slot = schedule.slot
                order.pickup_start_at = schedule.start_at
                order.pickup_end_at = schedule.end_at
                order.cutoff_at = schedule.cutoff_at
                order.stall_label = schedule.slot.farmer_market.stall_label
                update_fields += [
                    "pickup_date",
                    "pickup_slot",
                    "pickup_start_at",
                    "pickup_end_at",
                    "cutoff_at",
                    "stall_label",
                ]

            if change.note is not None:
                order.note = change.note
                update_fields.append("note")

            # The new time was the answer to a market schedule change: the order fits again.
            if schedule is not None and order.reschedule_requested_at is not None:
                order.reschedule_requested_at = None
                update_fields.append("reschedule_requested_at")

            order.pending_change = None
            order.version += 1
            save_with_history(order, update_fields=update_fields, reason=history_reason)

            OrderStatusHistory.objects.create(
                order=order,
                from_status=OrderStatus.ACCEPTED,
                to_status=OrderStatus.ACCEPTED,
                transition=None,
                actor=actor,
                actor_role=ActorRole.FARMER,
                change_reason="Farmer approved change request",
                request_id=get_request_id(),
            )
            notify(
                recipient=order.customer,
                event_type=NotificationType.ORDER_CHANGE_APPROVED,
                context=build_order_context(order),
            )
        return order

    return run_with_retry_if_top_level(_execute)


def reject_change_request(
    *,
    order_id: int,
    farmer_id: int,
    expected_version: int | None,
    actor: Any | None = None,
    reason: str | None = None,
) -> Order:
    """FA-35: keep the original order and drop the change request (D-030)."""
    if expected_version is None:
        raise PreconditionRequiredError("The If-Match header is required.")
    if reason and len(reason) > REASON_MAX_LENGTH:
        raise BusinessValidationError(
            errors={"reason": [f"Reason must be at most {REASON_MAX_LENGTH} characters."]}
        )
    clean_reason = reason.strip() if reason else None

    def _execute() -> Order:
        with transaction.atomic():
            order = _lock_farmer_order(
                order_id=order_id, farmer_id=farmer_id, expected_version=expected_version, verb="rejected"
            )
            order.pending_change = None
            order.version += 1
            save_with_history(
                order,
                update_fields=["pending_change", "version", "updated_at"],
                reason=f"Order #{order.pk}: change request rejected",
            )

            OrderStatusHistory.objects.create(
                order=order,
                from_status=OrderStatus.ACCEPTED,
                to_status=OrderStatus.ACCEPTED,
                transition=None,
                actor=actor,
                actor_role=ActorRole.FARMER,
                change_reason=(
                    f"Farmer rejected change request: {clean_reason}"
                    if clean_reason
                    else "Farmer rejected change request"
                ),
                request_id=get_request_id(),
            )
            notify(
                recipient=order.customer,
                event_type=NotificationType.ORDER_CHANGE_REJECTED,
                context={
                    **build_order_context(order),
                    "reason": clean_reason or "The farmer could not accommodate the requested changes.",
                },
            )
        return order

    return run_with_retry_if_top_level(_execute)
