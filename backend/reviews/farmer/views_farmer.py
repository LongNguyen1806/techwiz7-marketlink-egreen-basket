from typing import Any

from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from marketlink_core.exceptions import BusinessValidationError
from marketlink_core.pagination import StandardPagination
from marketlink_core.permissions import IsFarmer
from marketlink_core.responses import api_response
from reviews.farmer.serializers_farmer import ReplyReviewFarmerSerializer
from reviews.models import FarmerReview, ProductReview
from reviews.selectors import (
    TYPE_FARMER,
    TYPE_PRODUCT,
    farmer_reviews_of,
    product_reviews_of,
    serialize_review,
)
from reviews.services import reply_to_review

BOOLEAN_VALUES = {"true": True, "false": False}


def _parse_filters(params: Any) -> dict[str, Any]:
    errors: dict[str, list[str]] = {}
    review_type = (params.get("type") or "").strip().upper() or None
    if review_type not in (None, TYPE_FARMER, TYPE_PRODUCT):
        errors["type"] = [f"Use {TYPE_FARMER} or {TYPE_PRODUCT}."]
    rating = (params.get("rating") or "").strip() or None
    if rating is not None and rating not in {"1", "2", "3", "4", "5"}:
        errors["rating"] = ["Must be an integer from 1 to 5."]
    replied = (params.get("replied") or "").strip().lower() or None
    if replied is not None and replied not in BOOLEAN_VALUES:
        errors["replied"] = ["Use true or false."]
    if errors:
        raise BusinessValidationError("Invalid query parameters.", errors=errors)
    return {
        "type": review_type,
        "rating": int(rating) if rating else None,
        "replied": BOOLEAN_VALUES[replied] if replied else None,
    }


class FarmerReviewBaseView(APIView):
    permission_classes = [IsFarmer]


class FarmerReviewListView(FarmerReviewBaseView):
    def get(self, request: Request) -> Response:
        """FA-28: reviews of my stall and my products, newest first; hidden ones are flagged."""
        filters = _parse_filters(request.query_params)
        sources = []
        if filters["type"] in (None, TYPE_FARMER):
            sources.append((TYPE_FARMER, farmer_reviews_of(request.user.pk)))
        if filters["type"] in (None, TYPE_PRODUCT):
            sources.append((TYPE_PRODUCT, product_reviews_of(request.user.pk)))

        keys: list[tuple[Any, int, str]] = []
        for review_type, queryset in sources:
            if filters["rating"] is not None:
                queryset = queryset.filter(rating=filters["rating"])
            if filters["replied"] is not None:
                queryset = queryset.filter(reply__isnull=not filters["replied"])
            keys += [(created_at, pk, review_type) for pk, created_at in queryset.values_list("id", "created_at")]
        keys.sort(key=lambda key: (key[0], key[1]), reverse=True)

        paginator = StandardPagination()
        page = paginator.paginate_queryset(keys, request, view=self)
        loaded = {
            TYPE_FARMER: farmer_reviews_of(request.user.pk).in_bulk(
                [pk for _, pk, kind in page if kind == TYPE_FARMER]
            ),
            TYPE_PRODUCT: product_reviews_of(request.user.pk).in_bulk(
                [pk for _, pk, kind in page if kind == TYPE_PRODUCT]
            ),
        }
        return paginator.get_paginated_response([serialize_review(loaded[kind][pk]) for _, pk, kind in page])


class _FarmerReplyView(FarmerReviewBaseView):
    review_type = TYPE_FARMER

    def post(self, request: Request, review_id: int) -> Response:
        serializer = ReplyReviewFarmerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reply_to_review(
            review_type=self.review_type,
            review_id=review_id,
            farmer_id=request.user.pk,
            reply=serializer.validated_data["reply"],
        )
        source = farmer_reviews_of if self.review_type == TYPE_FARMER else product_reviews_of
        review: FarmerReview | ProductReview = source(request.user.pk).get(pk=review_id)
        return api_response(message="Reply posted.", data=serialize_review(review), request=request)


class FarmerReviewReplyView(_FarmerReplyView):
    """FA-29: POST /api/farmer/farmer-reviews/<id>/reply/."""

    review_type = TYPE_FARMER


class ProductReviewReplyView(_FarmerReplyView):
    """FA-30: POST /api/farmer/product-reviews/<id>/reply/."""

    review_type = TYPE_PRODUCT
