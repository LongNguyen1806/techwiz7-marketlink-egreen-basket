from decimal import Decimal
from typing import Any

from django.db import transaction
from django.utils import timezone

from accounts.models import FarmerStatus
from catalog.services.stock import lock_products
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
from notifications.models import NotificationType
from notifications.services import notify
from orders.models import ActorRole, Order, OrderStatus, OrderStatusHistory
from orders.services.fsm import run_with_retry_if_top_level
from orders.services.notification_context import build_order_context


def mark_order_item_sold_out(
    *,
    order_id: int,
    product_id: int,
    actor: Any,
    expected_version: int | None,
) -> Order:
    """FA-36: remove a sold-out item from a PLACED order and set its stock to 0.

    The order stays PLACED; after calling the customer the farmer accepts the rest (T2)
    or declines the order (T3). Lock order: orders -> order_items -> products.
    """
    if expected_version is None:
        raise PreconditionRequiredError("The If-Match header is required.")

    def _execute() -> Order:
        with transaction.atomic():
            order = (
                Order.objects.select_for_update(of=("self",))
                .select_related("farmer__user", "market", "customer__customer_profile")
                .filter(id=order_id)
                .first()
            )
            if order is None or order.farmer_id != getattr(actor, "pk", None):
                raise ResourceNotFoundError("Order not found.", code=ErrorCode.NOT_FOUND)
            if order.farmer.status == FarmerStatus.SUSPENDED:
                raise ForbiddenActionError(
                    "Your stall is suspended, so orders cannot be updated.",
                    code=ErrorCode.FARMER_SUSPENDED,
                )
            if order.version != expected_version:
                raise ConflictError(
                    "This order was just updated by someone else. Please reload.",
                    code=ErrorCode.RESOURCE_MODIFIED,
                )
            if order.status != OrderStatus.PLACED:
                raise UnprocessableEntityError(
                    "Items can be marked sold out only on orders waiting for approval.",
                    code=ErrorCode.FAILED_PRECONDITION,
                )
            if timezone.now() >= order.pickup_start_at:
                raise UnprocessableEntityError(
                    "The pickup time has already started.",
                    code=ErrorCode.PICKUP_ALREADY_STARTED,
                )

            items = list(order.items.select_for_update().order_by("id"))
            target = next((item for item in items if item.product_id == product_id), None)
            if target is None:
                raise ResourceNotFoundError(
                    "This product is not part of the order.", code=ErrorCode.NOT_FOUND
                )
            if len(items) == 1:
                raise BusinessValidationError(
                    "This is the only item in the order. Decline the order instead.",
                    errors={"product_id": ["An order must keep at least one item."]},
                )

            history_reason = f"Order #{order.pk}: item marked sold out ({target.product_name})"
            for product in lock_products(product_ids=[product_id]).values():
                if product.stock_quantity != 0:
                    product.stock_quantity = 0
                    save_with_history(
                        product, update_fields=["stock_quantity", "updated_at"], reason=history_reason
                    )

            removed_name = target.product_name
            remaining = [item for item in items if item.pk != target.pk]
            delete_with_history(target, reason=history_reason)  # keeps quantity and price in the trail
            order.total_amount = sum((item.line_total for item in remaining), Decimal("0.00"))
            order.version += 1
            save_with_history(
                order, update_fields=["total_amount", "version", "updated_at"], reason=history_reason
            )

            OrderStatusHistory.objects.create(
                order=order,
                from_status=OrderStatus.PLACED,
                to_status=OrderStatus.PLACED,
                transition=None,
                actor=actor,
                actor_role=ActorRole.FARMER,
                change_reason=f"Farmer marked out of stock: {removed_name}",
                request_id=get_request_id(),
            )
            notify(
                recipient=order.customer,
                event_type=NotificationType.ORDER_ITEM_SOLD_OUT,
                context={**build_order_context(order), "product_name": removed_name},
            )
        return order

    return run_with_retry_if_top_level(_execute)
