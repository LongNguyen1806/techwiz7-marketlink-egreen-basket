from django.db import IntegrityError, transaction

from marketlink_core.exceptions import ResourceNotFoundError
from orders.models import Order, OrderItem, OrderStatus
from reviews.exceptions import ReviewNotAllowedError
from reviews.models import FarmerReview, ProductReview

# D-016: only COMPLETED orders, one Farmer review per order, one review per order item.
# The UNIQUE indexes on farmer_reviews.order_id / product_reviews.order_item_id are the final guard.


def _own_order(*, customer, order_id: int) -> Order:
    # Someone else's order is "not found", so ids cannot be probed.
    order = Order.objects.filter(pk=order_id, customer=customer).first()
    if order is None:
        raise ResourceNotFoundError()
    return order


def _require_completed(order: Order) -> None:
    if order.status != OrderStatus.COMPLETED:
        raise ReviewNotAllowedError()


def _farmer_review_exists(order: Order) -> bool:
    return FarmerReview.objects.filter(order=order).exists()


def _product_review_exists(item: OrderItem) -> bool:
    return ProductReview.objects.filter(order_item=item).exists()


def _create_once(model, **fields):
    try:
        with transaction.atomic():
            return model.objects.create(**fields)
    except IntegrityError as exc:
        # A concurrent request saved the same review first.
        raise ReviewNotAllowedError() from exc


def create_farmer_review(*, customer, order_id: int, rating: int, comment: str | None = None) -> FarmerReview:
    """CU-10."""
    order = _own_order(customer=customer, order_id=order_id)
    _require_completed(order)
    if _farmer_review_exists(order):
        raise ReviewNotAllowedError()
    return _create_once(FarmerReview, order=order, rating=rating, comment=comment)


def create_product_review(*, customer, order_id: int, item_id: int, rating: int, comment: str | None = None) -> ProductReview:
    """CU-11: the item must belong to the order in the URL."""
    order = _own_order(customer=customer, order_id=order_id)
    item = order.items.filter(pk=item_id).first()
    if item is None:
        raise ResourceNotFoundError()
    _require_completed(order)
    if _product_review_exists(item):
        raise ReviewNotAllowedError()
    return _create_once(ProductReview, order_item=item, rating=rating, comment=comment)
