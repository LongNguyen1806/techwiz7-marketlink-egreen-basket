from django.db.models import Count, Prefetch

from catalog.selectors import public_products
from catalog.services.stock import get_held_quantities
from orders.models import Order, OrderItem, OrderStatus, OrderStatusHistory

# C-04 "Open" tab; every other status is "History".
OPEN_TAB = (OrderStatus.PLACED, OrderStatus.ACCEPTED, OrderStatus.READY_FOR_PICKUP)


def order_summary_queryset(order_ids):
    """Everything OrderSummaryReadSerializer reads, in a single query."""
    return (
        Order.objects.filter(pk__in=order_ids)
        .select_related("customer__customer_profile", "farmer", "market")
        .annotate(item_count=Count("items"))
        .order_by("id")
    )


def customer_orders_queryset(customer, *, tab=None, status=None, farmer_id=None, pickup_from=None,
                             pickup_to=None, ordering=None):
    """CU-05: the customer's own orders, filtered; C-04 default order depends on the tab."""
    orders = (
        Order.objects.filter(customer=customer)
        .select_related("customer__customer_profile", "farmer", "market")
        .annotate(item_count=Count("items"))
    )
    if tab == "open":
        orders = orders.filter(status__in=OPEN_TAB)
    elif tab == "history":
        orders = orders.exclude(status__in=OPEN_TAB)
    if status:
        orders = orders.filter(status__in=status)
    if farmer_id:
        orders = orders.filter(farmer_id=farmer_id)
    if pickup_from:
        orders = orders.filter(pickup_date__gte=pickup_from)
    if pickup_to:
        orders = orders.filter(pickup_date__lte=pickup_to)
    ordering = ordering or ("pickup_start_at" if tab == "open" else "-created_at")
    return orders.order_by(ordering, "-id" if ordering.startswith("-") else "id")


def customer_order_detail(customer, order_id) -> Order | None:
    """CU-06: one of the customer's own orders with everything OrderDetail reads; None if not theirs."""
    return (
        Order.objects.filter(pk=order_id, customer=customer)
        .select_related("customer__customer_profile", "farmer", "market", "farmer_review")
        .annotate(item_count=Count("items"))
        .prefetch_related(
            Prefetch("items", queryset=OrderItem.objects.select_related("product", "product_review")),
            Prefetch(
                "status_history",
                queryset=OrderStatusHistory.objects.select_related(
                    "actor__farmer_profile", "actor__customer_profile"
                ),
            ),
        )
        .first()
    )


def reorder_items(order) -> tuple[list[tuple], list[dict]]:
    """CU-09 (D-019, A-015): the order's lines split into what can go back in the cart and what cannot.

    Read-only. A product is skipped as UNAVAILABLE when it is no longer publicly on sale, and as
    OUT_OF_STOCK when no stock is available — the same availability checkout enforces (D-029), so the
    preview never offers an item checkout would reject. Quantities stay as they were; the cart page warns
    when one exceeds the stock left.
    """
    lines = list(order.items.all())
    product_ids = [item.product_id for item in lines]
    on_sale = public_products(in_stock=False).in_bulk(product_ids)
    held = get_held_quantities(product_ids=product_ids)

    kept, skipped = [], []
    for item in lines:
        product = on_sale.get(item.product_id)
        if product is None or not product.is_available:
            reason = "UNAVAILABLE"
        elif product.stock_quantity - held.get(product.pk, 0) < product.min_per_order:
            # Less left than the stall's minimum per order is as good as sold out for a new order.
            reason = "OUT_OF_STOCK"
        else:
            # The stall may have moved its per-order window since; the cart gets a quantity inside it.
            quantity = max(item.quantity, product.min_per_order)
            if product.max_per_order:
                quantity = min(quantity, product.max_per_order)
            kept.append((product, quantity))
            continue
        skipped.append({"product_id": item.product_id, "product_name": item.product_name, "reason": reason})
    return kept, skipped
