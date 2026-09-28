from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from accounts.selectors import public_farmer
from catalog.selectors import public_product
from marketlink_core.pagination import PublicReviewPagination
from reviews.public_portal.serializers_public import (
    PublicReviewSerializer,
    RatingSummarySerializer,
    serialize_public_review,
)
from reviews.selectors import (
    RATING_VALUES,
    ReviewType,
    public_farmer_reviews,
    public_product_reviews,
    rating_summary,
)

RATING_PARAM = [OpenApiParameter("rating", int, enum=list(RATING_VALUES))]


def star_filter(raw: str | None) -> int | None:
    try:
        value = int(raw) if raw is not None else None
    except ValueError:
        return None
    return value if value in RATING_VALUES else None


class _PublicReviewListView(ListAPIView):
    permission_classes = [AllowAny]
    pagination_class = PublicReviewPagination
    serializer_class = PublicReviewSerializer
    review_type: str = ""

    def _unfiltered(self, target_id: int):
        raise NotImplementedError

    def _filtered(self, target_id: int, rating: int | None):
        raise NotImplementedError

    def get(self, request, *args, **kwargs):
        target_id = kwargs["id"]
        rating = star_filter(request.query_params.get("rating"))
        page = self.paginate_queryset(self._filtered(target_id, rating))
        rows = [serialize_public_review(self.review_type, review) for review in page]
        response = self.paginator.get_paginated_response(
            PublicReviewSerializer(rows, many=True).data
        )
        response.data["data"]["summary"] = RatingSummarySerializer(
            rating_summary(self._unfiltered(target_id))
        ).data
        return response


class PublicFarmerReviewListView(_PublicReviewListView):
    review_type = ReviewType.FARMER

    def _unfiltered(self, target_id):
        return public_farmer_reviews(farmer_id=target_id)

    def _filtered(self, target_id, rating):
        public_farmer(farmer_id=target_id)
        return public_farmer_reviews(farmer_id=target_id, rating=rating)

    @extend_schema(parameters=RATING_PARAM, responses={200: PublicReviewSerializer(many=True), 404: None})
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class PublicProductReviewListView(_PublicReviewListView):
    review_type = ReviewType.PRODUCT

    def _unfiltered(self, target_id):
        return public_product_reviews(product_id=target_id)

    def _filtered(self, target_id, rating):
        public_product(product_id=target_id)
        return public_product_reviews(product_id=target_id, rating=rating)

    @extend_schema(parameters=RATING_PARAM, responses={200: PublicReviewSerializer(many=True), 404: None})
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)
