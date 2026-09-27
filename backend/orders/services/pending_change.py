"""Shared contract for ``orders.pending_change`` (D-030, D-036).

Stored format (written by CU-07, read by FA-34 and OrderDetail)::

    {
        "items": [{"product_id": int, "quantity": int >= 1, "unit_price": "2.50"}] | null,
        "pickup_date": "YYYY-MM-DD" | null,      # sent together with pickup_slot_id
        "pickup_slot_id": int | null,
        "note": str | null,                      # null = note unchanged
        "requested_at": ISO datetime,
    }

``unit_price`` is the price the customer saw when sending the request: kept items keep
their order price, new items use the product price at request time (decision A, v1.8).
Extra keys (product_name, unit, change_summary...) are allowed and ignored.
"""

import logging
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from django.utils import timezone
from rest_framework import serializers

from catalog.models import Product
from marketlink_core.exceptions import ErrorCode, UnprocessableEntityError
from markets.models import PickupSlot
from orders.models import Order

logger = logging.getLogger("marketlink")

NOTE_MAX_LENGTH = 300
_DATETIME_FIELD = serializers.DateTimeField()


@dataclass(frozen=True)
class PendingItem:
    product_id: int
    quantity: int
    unit_price: Decimal


@dataclass(frozen=True)
class PendingChange:
    items: list[PendingItem] | None
    pickup_date: date | None
    pickup_slot_id: int | None
    note: str | None
    requested_at: str | None


def _invalid(field: str, message: str) -> UnprocessableEntityError:
    return UnprocessableEntityError(
        "The change request data is invalid. Please ask the customer to send it again.",
        code=ErrorCode.FAILED_PRECONDITION,
        errors={f"pending_change.{field}": [message]},
    )


def _positive_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _parse_items(raw_items: Any) -> list[PendingItem] | None:
    if raw_items is None:
        return None
    if not isinstance(raw_items, list) or not raw_items:
        raise _invalid("items", "Must be a non-empty list or null.")
    items: list[PendingItem] = []
    seen: set[int] = set()
    for index, entry in enumerate(raw_items):
        if not isinstance(entry, dict):
            raise _invalid(f"items.{index}", "Must be an object.")
        product_id, quantity = entry.get("product_id"), entry.get("quantity")
        if not _positive_int(product_id) or not _positive_int(quantity):
            raise _invalid(f"items.{index}", "product_id and quantity must be integers >= 1.")
        if product_id in seen:
            raise _invalid(f"items.{index}", "Duplicate product.")
        seen.add(product_id)
        try:
            unit_price = Decimal(str(entry["unit_price"]))
        except (KeyError, InvalidOperation):
            raise _invalid(f"items.{index}.unit_price", "A valid unit_price is required.") from None
        if not unit_price.is_finite() or unit_price < 0:
            raise _invalid(f"items.{index}.unit_price", "A valid unit_price is required.")
        items.append(PendingItem(product_id=product_id, quantity=quantity, unit_price=unit_price))
    return items


def parse_pending_change(raw: Any) -> PendingChange:
    """Validate the stored JSON; raise 422 FAILED_PRECONDITION instead of crashing."""
    if not isinstance(raw, dict):
        raise _invalid("root", "Must be an object.")

    raw_date, slot_id = raw.get("pickup_date"), raw.get("pickup_slot_id")
    if (raw_date is None) != (slot_id is None):
        raise _invalid("pickup_date", "pickup_date and pickup_slot_id must be sent together.")
    pickup_date = None
    if raw_date is not None:
        if not isinstance(raw_date, str) or not _positive_int(slot_id):
            raise _invalid("pickup_date", "Invalid pickup date or slot.")
        try:
            pickup_date = date.fromisoformat(raw_date)
        except ValueError:
            raise _invalid("pickup_date", "Use the YYYY-MM-DD format.") from None

    note = raw.get("note")
    if note is not None and (not isinstance(note, str) or len(note) > NOTE_MAX_LENGTH):
        raise _invalid("note", f"Must be text of at most {NOTE_MAX_LENGTH} characters.")

    requested_at = raw.get("requested_at")
    return PendingChange(
        items=_parse_items(raw.get("items")),
        pickup_date=pickup_date,
        pickup_slot_id=slot_id,
        note=note,
        requested_at=requested_at if isinstance(requested_at, str) else None,
    )


def _money(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def _datetime(value: datetime | None) -> str | None:
    return _DATETIME_FIELD.to_representation(value) if value is not None else None


def _new_schedule(order: Order, change: PendingChange) -> tuple[datetime, datetime, datetime] | None:
    if change.pickup_date is None:
        return None
    slot = (
        PickupSlot.objects.select_related("farmer_market")
        .filter(id=change.pickup_slot_id, farmer_market__farmer_id=order.farmer_id)
        .first()
    )
    if slot is None:
        return None
    tz = timezone.get_current_timezone()
    start_at = timezone.make_aware(datetime.combine(change.pickup_date, slot.start_time), tz)
    end_at = timezone.make_aware(datetime.combine(change.pickup_date, slot.end_time), tz)
    return start_at, end_at, start_at - timedelta(hours=order.farmer.order_cutoff_hours)


def present_pending_change(order: Order) -> dict[str, Any] | None:
    """Build OrderDetail.pending_change (Pass 4B §3.4) for the farmer screen F-03."""
    if not order.pending_change:
        return None
    try:
        change = parse_pending_change(order.pending_change)
    except UnprocessableEntityError:
        # Never break the order detail page; FA-34 reports the problem when the farmer acts.
        logger.warning("Order %s has an invalid pending_change", order.pk)
        return None

    current_items = {item.product_id: item for item in order.items.all()}
    items_data = None
    estimated_total = order.total_amount
    if change.items is not None:
        products = Product.objects.in_bulk([item.product_id for item in change.items])
        items_data = []
        estimated_total = Decimal("0.00")
        for item in change.items:
            product = products.get(item.product_id)
            current = current_items.get(item.product_id)
            estimated_total += item.unit_price * item.quantity
            items_data.append(
                {
                    "product_id": item.product_id,
                    "product_name": product.name if product else (current.product_name if current else ""),
                    "unit": product.unit if product else (current.unit if current else ""),
                    "quantity": item.quantity,
                    "current_quantity": current.quantity if current else 0,
                    "stock_available": product.stock_quantity if product else 0,
                    "unit_price": _money(item.unit_price),
                }
            )

    schedule = _new_schedule(order, change)
    return {
        "items": items_data,
        "pickup_slot_id": change.pickup_slot_id,
        "pickup_date": change.pickup_date.isoformat() if change.pickup_date else None,
        "pickup_start_at": _datetime(schedule[0]) if schedule else None,
        "pickup_end_at": _datetime(schedule[1]) if schedule else None,
        "cutoff_at": _datetime(schedule[2]) if schedule else None,
        "note": change.note,
        "estimated_total": _money(estimated_total),
        "requested_at": change.requested_at,
        "expires_at": _datetime(order.pickup_start_at),
    }
