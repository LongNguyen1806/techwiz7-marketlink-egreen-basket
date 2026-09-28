from datetime import date
from typing import Any

from django.db import models, transaction
from django.utils import timezone

from catalog.services.stock import lock_products
from orders.services.checkout_service import cap_message, minimum_message
from marketlink_core.context import get_request_id
from marketlink_core.exceptions import (
    BusinessValidationError,
    ConflictError,
    ErrorCode,
    ForbiddenActionError,
    PreconditionRequiredError,
    UnprocessableEntityError,
)
from markets.services.validation import validate_pickup_date
from notifications.models import NotificationType
from notifications.services import notify
from orders.models import ActorRole, Order, OrderItem, OrderStatus, OrderStatusHistory
from orders.services.notification_context import build_order_context


def modify_order(
    *,
    order_id: int,
    actor: Any,
    expected_version: int | None,
    items_data: list[dict[str, Any]] | None = None,
    pickup_date: date | None = None,
    pickup_slot_id: int | None = None,
    note: str | None = None,
) -> Order:
    if expected_version is None:
        raise PreconditionRequiredError("The If-Match header is required.")

    with transaction.atomic():
        order = (
            Order.objects.select_for_update(of=("self",))
            .select_related("farmer__user", "market", "customer")
            .get(id=order_id)
        )

        if order.version != expected_version:
            raise ConflictError(
                "This order was just updated by someone else. Please reload.",
                code=ErrorCode.RESOURCE_MODIFIED,
            )

        actor_id = getattr(actor, "pk", None)
        if order.customer_id != actor_id:
            raise ForbiddenActionError(code=ErrorCode.ACTION_NOT_PERMITTED_FOR_ROLE)

        if order.status not in (OrderStatus.PLACED, OrderStatus.ACCEPTED):
            raise BusinessValidationError(
                f"Orders in status {order.status} cannot be modified.",
                code=ErrorCode.INVALID_STATUS_TRANSITION,
            )

        now = timezone.now()
        # The market changed its schedule under this order. The old cutoff no longer means
        # anything, so it does not lock the shopper out; the new time still has to pass every
        # rule (market day and hours, closures, the stall's own cutoff) in validate_pickup_date.
        rescheduling = order.reschedule_requested_at is not None
        if rescheduling:
            if pickup_date is None or pickup_slot_id is None:
                raise BusinessValidationError(
                    "Please choose a new pickup date and time.",
                    code=ErrorCode.VALIDATION_ERROR,
                    errors={"pickup_slot_id": ["Please choose a new pickup time."]},
                )
            if items_data is not None and {
                entry.get("product_id"): entry.get("quantity") for entry in items_data
            } != {item.product_id: item.quantity for item in order.items.all()}:
                raise BusinessValidationError(
                    "Only the pickup time can change on this order.",
                    code=ErrorCode.VALIDATION_ERROR,
                )
            items_data = None
        elif now >= order.cutoff_at:
            raise UnprocessableEntityError(
                "The cutoff time for modifying this order has passed.",
                code=ErrorCode.CUTOFF_PASSED,
            )

        changes: list[str] = []
        clean_note: str | None = None

        if note is not None:
            clean_note = note.strip()
            if len(clean_note) > 300:
                raise BusinessValidationError(
                    errors={"note": ["Note must be at most 300 characters."]}
                )
            if order.note != clean_note:
                changes.append("note updated")

        validated_schedule = None
        if pickup_date is not None or pickup_slot_id is not None:
            if pickup_date is None or pickup_slot_id is None:
                raise BusinessValidationError(
                    "Both pickup_date and pickup_slot_id are required to change pickup timing.",
                    code=ErrorCode.VALIDATION_ERROR,
                )

            validated_schedule = validate_pickup_date(
                farmer_id=order.farmer_id,
                market_id=order.market_id,
                pickup_date=pickup_date,
                pickup_slot_id=pickup_slot_id,
            )

            if order.pickup_date != pickup_date or order.pickup_slot_id != validated_schedule.slot.id:
                slot_label = (
                    f"{validated_schedule.slot.start_time.strftime('%H:%M')}–{validated_schedule.slot.end_time.strftime('%H:%M')}"
                )
                changes.append(
                    f"rescheduled to {pickup_date.strftime('%Y-%m-%d')} ({slot_label})"
                )

        new_items_dict: dict[int, int] | None = None
        old_items = {item.product_id: item for item in order.items.all()}
        all_product_ids: list[int] = sorted(old_items.keys())
        locked_products = {}

        if items_data is not None:
            if not items_data:
                raise BusinessValidationError(
                    "An order must have at least one item. To cancel the order, please use cancel order.",
                    code=ErrorCode.VALIDATION_ERROR,
                )

            new_items_dict = {}
            for idx, entry in enumerate(items_data):
                pid = entry.get("product_id")
                qty = entry.get("quantity")
                if not pid or not isinstance(qty, int) or qty <= 0:
                    raise BusinessValidationError(
                        errors={f"items.{idx}": ["Product ID and quantity >= 1 are required."]},
                        code=ErrorCode.VALIDATION_ERROR,
                    )
                if pid in new_items_dict:
                    raise BusinessValidationError(
                        errors={f"items.{idx}": ["Duplicate product in items list."]},
                        code=ErrorCode.VALIDATION_ERROR,
                    )
                new_items_dict[pid] = qty

            all_product_ids = sorted(set(old_items.keys()) | set(new_items_dict.keys()))
            locked_products = lock_products(product_ids=all_product_ids)

            for pid, new_qty in new_items_dict.items():
                prod = locked_products.get(pid)
                if not prod or prod.farmer_id != order.farmer_id:
                    raise UnprocessableEntityError(
                        f"Product {pid} does not belong to this farmer.",
                        code=ErrorCode.PRODUCT_NOT_AVAILABLE,
                    )
                old_qty = old_items[pid].quantity if pid in old_items else 0
                # Keeping or lowering a line is always allowed, so an order whose product went back
                # into review (or had its cap lowered) can still be edited down.
                if new_qty > old_qty and not prod.is_on_sale:
                    raise UnprocessableEntityError(
                        f"Product {prod.name} is not available.",
                        code=ErrorCode.PRODUCT_NOT_AVAILABLE,
                    )
                # A line the customer adds or changes must sit in the stall's per-order window;
                # an untouched line keeps its old quantity even if the window moved since.
                if new_qty != old_qty and new_qty < prod.min_per_order:
                    raise BusinessValidationError(
                        minimum_message(prod),
                        code=ErrorCode.VALIDATION_ERROR,
                        errors={str(pid): [minimum_message(prod)]},
                    )
                if new_qty > old_qty and prod.max_per_order is not None and new_qty > prod.max_per_order:
                    raise BusinessValidationError(
                        cap_message(prod),
                        code=ErrorCode.VALIDATION_ERROR,
                        errors={str(pid): [cap_message(prod)]},
                    )

            # Check stock availability for increases without physical deduction
            shortages: dict[str, list[str]] = {}
            for pid in all_product_ids:
                old_qty = old_items[pid].quantity if pid in old_items else 0
                new_qty = new_items_dict.get(pid, 0)
                if old_qty != new_qty:
                    prod = locked_products[pid]
                    prod_name = prod.name
                    if old_qty == 0:
                        changes.append(f"added {prod_name} x{new_qty}")
                    elif new_qty == 0:
                        changes.append(f"removed {prod_name}")
                    else:
                        changes.append(f"{prod_name} {old_qty}->{new_qty}")

                    if new_qty > old_qty:
                        diff = new_qty - old_qty
                        held_by_others = (
                            OrderItem.objects.filter(
                                product_id=pid,
                                order__status=OrderStatus.PLACED,
                                order__pickup_start_at__gt=now,
                            )
                            .exclude(order_id=order.id)
                            .aggregate(total=models.Sum("quantity"))["total"]
                            or 0
                        )
                        available = max(prod.stock_quantity - held_by_others, 0)
                        if order.status == OrderStatus.ACCEPTED:
                            # ACCEPTED orders already had old_qty deducted from physical stock
                            if diff > available:
                                shortages[str(pid)] = [
                                    f"Only {available} {prod.unit.lower()} available."
                                ]
                        else:
                            if new_qty > available:
                                shortages[str(pid)] = [
                                    f"Only {available} {prod.unit.lower()} available."
                                ]
            if shortages:
                raise BusinessValidationError(
                    "Some items are out of stock.",
                    code=ErrorCode.INSUFFICIENT_STOCK,
                    errors=shortages,
                )

        if not changes:
            return order

        change_summary = "; ".join(changes)
        if len(change_summary) > 500:
            change_summary = change_summary[:497] + "..."

        order.version += 1

        # An accepted order moved by the market's schedule change goes the usual way too: the new
        # time is a request the stall approves. The order stays marked until it does.
        if order.status == OrderStatus.ACCEPTED:
            # ACCEPTED orders preserve current state and store pending_change for farmer review (D-030)
            pending_items = None
            if new_items_dict is not None:
                pending_items = [
                    {
                        "product_id": pid,
                        "product_name": locked_products[pid].name,
                        "quantity": qty,
                        "unit": locked_products[pid].unit,
                        "unit_price": str(old_items[pid].unit_price if pid in old_items else locked_products[pid].price),
                    }
                    for pid, qty in new_items_dict.items()
                ]

            order.pending_change = {
                "items": pending_items,
                "pickup_date": pickup_date.isoformat() if pickup_date is not None else None,
                "pickup_slot_id": pickup_slot_id if pickup_slot_id is not None else None,
                "note": clean_note if clean_note is not None else None,
                "change_summary": change_summary,
                "requested_at": now.isoformat(),
            }
            order.save(update_fields=["pending_change", "version", "updated_at"])

            OrderStatusHistory.objects.create(
                order=order,
                from_status=OrderStatus.ACCEPTED,
                to_status=OrderStatus.ACCEPTED,
                transition=None,
                actor=actor,
                actor_role=ActorRole.CUSTOMER,
                change_reason=f"Change request submitted: {change_summary}",
                request_id=get_request_id(),
            )
        else:
            # PLACED orders (and rescheduled ones) apply changes directly to database
            from_status = order.status
            if clean_note is not None:
                order.note = clean_note

            if validated_schedule is not None:
                order.pickup_date = pickup_date
                order.pickup_slot = validated_schedule.slot
                order.pickup_start_at = validated_schedule.start_at
                order.pickup_end_at = validated_schedule.end_at
                order.cutoff_at = validated_schedule.cutoff_at
                order.stall_label = validated_schedule.slot.farmer_market.stall_label

            if new_items_dict is not None:
                for pid, old_item in old_items.items():
                    if pid not in new_items_dict:
                        old_item.delete()

                for pid, qty in new_items_dict.items():
                    prod = locked_products[pid]
                    if pid in old_items:
                        old_item = old_items[pid]
                        if old_item.quantity != qty:
                            old_item.quantity = qty
                            old_item.line_total = old_item.unit_price * qty
                            old_item.save(update_fields=["quantity", "line_total", "updated_at"])
                    else:
                        OrderItem.objects.create(
                            order=order,
                            product=prod,
                            product_name=prod.name,
                            unit=prod.unit,
                            unit_price=prod.price,
                            quantity=qty,
                            line_total=prod.price * qty,
                        )

                order.total_amount = sum(item.line_total for item in order.items.all())

            update_fields = [
                "version",
                "updated_at",
                "total_amount",
                "note",
                "pickup_date",
                "pickup_slot",
                "pickup_start_at",
                "pickup_end_at",
                "cutoff_at",
                "stall_label",
            ]
            if rescheduling:
                order.reschedule_requested_at = None
                update_fields.append("reschedule_requested_at")
            order.save(update_fields=update_fields)

            OrderStatusHistory.objects.create(
                order=order,
                from_status=from_status,
                to_status=from_status,
                transition=None,
                actor=actor,
                actor_role=ActorRole.CUSTOMER,
                change_reason=(
                    f"Customer picked a new time after the market changed: {change_summary}"
                    if rescheduling
                    else f"Customer modified: {change_summary}"
                ),
                request_id=get_request_id(),
            )

        notify(
            recipient=order.farmer.user,
            event_type=NotificationType.ORDER_MODIFIED,
            context={**build_order_context(order), "change_summary": change_summary},
        )

    return order
