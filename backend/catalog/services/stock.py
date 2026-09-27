from collections.abc import Iterable
from typing import Any

from django.db.models import Sum
from django.utils import timezone

from catalog.models import Product
from marketlink_core.exceptions import BusinessValidationError, ErrorCode
from marketlink_core.history import UNSET, save_with_history
from orders.models import OrderItem, OrderStatus


def lock_products(*, product_ids: Iterable[int]) -> dict[int, Product]:
    ids = sorted(set(product_ids))
    products = list(Product.objects.filter(id__in=ids).order_by("id").select_for_update(of=("self",)))
    return {product.id: product for product in products}


def apply_stock_delta(
    *,
    products: dict[int, Product],
    deltas: dict[int, int],
    reason: str | None = None,
    user: Any = UNSET,
) -> None:
    """Add deltas (negative = take stock). Each change gets a product history row (v1.8 audit
    trail) stamped with `reason`, e.g. "Order #12 accepted (T2)"; `user=None` marks a system action."""
    shortages = {
        str(product_id): [f"Only {products[product_id].stock_quantity} {products[product_id].unit.lower()} left."]
        for product_id, delta in deltas.items()
        if products[product_id].stock_quantity + delta < 0
    }
    if shortages:
        raise BusinessValidationError(
            "Some items are out of stock.", code=ErrorCode.INSUFFICIENT_STOCK, errors=shortages
        )
    for product_id, delta in deltas.items():
        if delta == 0:
            continue
        product = products[product_id]
        product.stock_quantity += delta
        save_with_history(product, update_fields=["stock_quantity", "updated_at"], reason=reason, user=user)


def get_held_quantities(*, product_ids: Iterable[int]) -> dict[int, int]:
    # Physical stock is deducted upon ACCEPTED; only active PLACED orders hold stock reservation.
    now = timezone.now()
    rows = (
        OrderItem.objects.filter(
            product_id__in=set(product_ids),
            order__status=OrderStatus.PLACED,
            order__pickup_start_at__gt=now,
        )
        .values("product_id")
        .annotate(held=Sum("quantity"))
    )
    return {row["product_id"]: row["held"] for row in rows}


def get_available_stock(*, product: Product) -> int:
    held = get_held_quantities(product_ids=[product.id]).get(product.id, 0)
    return max(product.stock_quantity - held, 0)


def get_weekly_pattern_held_quantities(*, product_ids: Iterable[int]) -> dict[int, int]:
    """Weekly template "held" (A-004, D-029): ACCEPTED / READY orders whose pickup window has not
    ended yet — orders being picked up right now still hold their goods. Orders past pickup_end_at
    belong to the previous cycle and are listed separately as overdue."""
    now = timezone.now()
    rows = (
        OrderItem.objects.filter(
            product_id__in=set(product_ids),
            order__status__in=[OrderStatus.ACCEPTED, OrderStatus.READY_FOR_PICKUP],
            order__pickup_end_at__gt=now,
        )
        .values("product_id")
        .annotate(held=Sum("quantity"))
    )
    return {row["product_id"]: row["held"] for row in rows}


def get_pending_quantities(*, product_ids: Iterable[int]) -> dict[int, int]:
    now = timezone.now()
    rows = (
        OrderItem.objects.filter(
            product_id__in=set(product_ids),
            order__status=OrderStatus.PLACED,
            order__pickup_start_at__gt=now,
        )
        .values("product_id")
        .annotate(pending=Sum("quantity"))
    )
    return {row["product_id"]: row["pending"] for row in rows}



def get_open_held_quantities(*, product_ids: Iterable[int]) -> dict[int, int]:
    """FarmerProduct.held_quantity (D-029, v1.8): every open ACCEPTED / READY order, including
    the ones already past their pickup time. Distinct from get_weekly_pattern_held_quantities,
    which drops those because the weekly template plans the next cycle (A-004)."""
    rows = (
        OrderItem.objects.filter(
            product_id__in=set(product_ids),
            order__status__in=[OrderStatus.ACCEPTED, OrderStatus.READY_FOR_PICKUP],
        )
        .values("product_id")
        .annotate(total=Sum("quantity"))
    )
    return {row["product_id"]: row["total"] for row in rows}
