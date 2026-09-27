"""Read-only review helpers shared by FA-28 now and the public / admin review screens later."""

from typing import Any

from django.db.models import QuerySet
from rest_framework import serializers

from reviews.models import FarmerReview, ProductReview

TYPE_FARMER = "FARMER"
TYPE_PRODUCT = "PRODUCT"
_DATETIME_FIELD = serializers.DateTimeField()


def customer_display_name(full_name: str | None) -> str:
    """U-05: "Nguyen Van A" -> "Nguyen V. A." (family name kept, other names as initials)."""
    parts = (full_name or "").split()
    if not parts:
        return "Customer"
    if len(parts) == 1:
        return parts[0]
    return " ".join([parts[0], *(f"{part[0].upper()}." for part in parts[1:])])


def farmer_reviews_of(farmer_id: int) -> QuerySet:
    """Reviews about the farmer's stall (FarmerReview.order.farmer = farmer)."""
    return FarmerReview.objects.filter(order__farmer_id=farmer_id).select_related(
        "order__customer__customer_profile"
    )


def product_reviews_of(farmer_id: int) -> QuerySet:
    """Reviews about the farmer's products (FA-30 scope: product.farmer = farmer)."""
    return ProductReview.objects.filter(order_item__product__farmer_id=farmer_id).select_related(
        "order_item__order__customer__customer_profile", "order_item__product"
    )


def _datetime(value: Any) -> str | None:
    return _DATETIME_FIELD.to_representation(value) if value is not None else None


def serialize_review(review: FarmerReview | ProductReview, *, include_hidden_reason: bool = False) -> dict[str, Any]:
    """Review (Pass 4B §3.x). hidden_reason is for Admin only; other callers get null."""
    if isinstance(review, ProductReview):
        item = review.order_item
        order, review_type = item.order, TYPE_PRODUCT
        product = {"id": item.product_id, "name": item.product.name if item.product else item.product_name}
    else:
        order, review_type, product = review.order, TYPE_FARMER, None
    profile = getattr(order.customer, "customer_profile", None)
    return {
        "id": review.pk,
        "type": review_type,
        "rating": review.rating,
        "comment": review.comment,
        "customer_display_name": customer_display_name(profile.full_name if profile else None),
        "product": product,
        "order_id": order.pk,
        "reply": review.reply,
        "replied_at": _datetime(review.replied_at),
        "is_hidden_by_admin": review.is_hidden_by_admin,
        "hidden_reason": review.hidden_reason if include_hidden_reason else None,
        "created_at": _datetime(review.created_at),
    }
