from collections import Counter
from collections.abc import Iterable

from django.db import models
from django.db.models import CharField, QuerySet, Value

from marketlink_core.ordering import both_directions, resolve_ordering
from reviews.models import FarmerReview, ProductReview


class ReviewType(models.TextChoices):
    PRODUCT = "PRODUCT", "Product"
    FARMER = "FARMER", "Farmer"


def _index(
    model,
    review_type: str,
    rating: int | None,
    is_hidden: bool | None,
    review_id: int | None = None,
) -> QuerySet:
    queryset = model.objects.all()
    if review_id is not None:
        queryset = queryset.filter(pk=review_id)
    if rating is not None:
        queryset = queryset.filter(rating=rating)
    if is_hidden is not None:
        queryset = queryset.filter(is_hidden_by_admin=is_hidden)
    return queryset.annotate(
        review_type=Value(review_type, output_field=CharField())
    ).values("id", "created_at", "review_type", "rating")


ADMIN_REVIEW_ORDERING = both_directions(
    {"created_at": ("created_at",), "rating": ("rating",)}
)
ADMIN_REVIEW_ORDERING["newest"] = ("-created_at", "-id")


def list_reviews_for_admin(
    *,
    review_type: str | None = None,
    review_id: int | None = None,
    rating: int | None = None,
    is_hidden: bool | None = None,
    ordering: str | None = None,
) -> QuerySet:
    if review_id is not None and review_type is None:
        review_id = None
    parts = []
    if review_type in (None, ReviewType.PRODUCT):
        parts.append(_index(ProductReview, ReviewType.PRODUCT, rating, is_hidden, review_id))
    if review_type in (None, ReviewType.FARMER):
        parts.append(_index(FarmerReview, ReviewType.FARMER, rating, is_hidden, review_id))
    combined = parts[0] if len(parts) == 1 else parts[0].union(*parts[1:])
    return combined.order_by(
        *resolve_ordering(ordering, allowed=ADMIN_REVIEW_ORDERING, default="newest")
    )


def product_reviews_by_id(*, review_ids: Iterable[int]) -> dict[int, ProductReview]:
    return ProductReview.objects.filter(id__in=set(review_ids)).select_related(
        "order_item__product", "order_item__order__customer__customer_profile"
    ).in_bulk()


def farmer_reviews_by_id(*, review_ids: Iterable[int]) -> dict[int, FarmerReview]:
    return FarmerReview.objects.filter(id__in=set(review_ids)).select_related(
        "order__customer__customer_profile"
    ).in_bulk()


def hydrate_reviews(rows: list[dict]) -> list[tuple[str, ProductReview | FarmerReview]]:
    products = product_reviews_by_id(
        review_ids=[r["id"] for r in rows if r["review_type"] == ReviewType.PRODUCT]
    )
    farmers = farmer_reviews_by_id(
        review_ids=[r["id"] for r in rows if r["review_type"] == ReviewType.FARMER]
    )
    hydrated = []
    for row in rows:
        source = products if row["review_type"] == ReviewType.PRODUCT else farmers
        review = source.get(row["id"])
        if review is not None:
            hydrated.append((row["review_type"], review))
    return hydrated


def get_review_for_admin(*, review_type: str, review_id: int):
    model = ProductReview if review_type == ReviewType.PRODUCT else FarmerReview
    lookup = (
        product_reviews_by_id(review_ids=[review_id])
        if review_type == ReviewType.PRODUCT
        else farmer_reviews_by_id(review_ids=[review_id])
    )
    review = lookup.get(review_id)
    if review is None:
        raise model.DoesNotExist
    return review


RATING_VALUES = (1, 2, 3, 4, 5)


def public_farmer_reviews(*, farmer_id: int, rating: int | None = None) -> QuerySet[FarmerReview]:
    queryset = FarmerReview.objects.filter(
        order__farmer_id=farmer_id, is_hidden_by_admin=False
    ).select_related("order__customer__customer_profile")
    if rating is not None:
        queryset = queryset.filter(rating=rating)
    return queryset.order_by("-created_at", "-id")


def public_product_reviews(*, product_id: int, rating: int | None = None) -> QuerySet[ProductReview]:
    queryset = ProductReview.objects.filter(
        order_item__product_id=product_id, is_hidden_by_admin=False
    ).select_related("order_item__product", "order_item__order__customer__customer_profile")
    if rating is not None:
        queryset = queryset.filter(rating=rating)
    return queryset.order_by("-created_at", "-id")


def rating_summary(queryset: QuerySet) -> dict:
    rows = queryset.values_list("rating", flat=True)
    counts = Counter(rows)
    total = sum(counts.values())
    average = sum(rating * count for rating, count in counts.items()) / total if total else None
    return {
        "rating_avg": round(average, 2) if average is not None else None,
        "rating_count": total,
        "distribution": {str(value): counts.get(value, 0) for value in RATING_VALUES},
    }

from reviews.farmer_selectors import (  # noqa: E402,F401
    TYPE_FARMER,
    TYPE_PRODUCT,
    customer_display_name,
    farmer_reviews_of,
    product_reviews_of,
    serialize_review,
)
