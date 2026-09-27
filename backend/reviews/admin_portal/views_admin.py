from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import ListAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from marketlink_core.exceptions import ResourceNotFoundError
from marketlink_core.permissions import IsAdmin
from marketlink_core.responses import api_response
from reviews.admin_portal.serializers_admin import (
    ReviewAdminSerializer,
    ReviewReasonSerializer,
    serialize_review,
)
from reviews.models import FarmerReview, ProductReview
from reviews.selectors import (
    ReviewType,
    get_review_for_admin,
    hydrate_reviews,
    list_reviews_for_admin,
)
from reviews.services.review_moderation_service import hide_review, restore_review
from system.models import AuditAction
from system.services import log_request_event
from reviews.selectors import ADMIN_REVIEW_ORDERING

RATING_RANGE = range(1, 6)


def _flag(raw: str | None) -> bool | None:
    if raw is None:
        return None
    lowered = raw.strip().lower()
    if lowered in ("true", "1"):
        return True
    if lowered in ("false", "0"):
        return False
    return None


def _rating(raw: str | None) -> int | None:
    try:
        value = int(raw) if raw is not None else None
    except ValueError:
        return None
    return value if value in RATING_RANGE else None


def _int(raw: str | None) -> int | None:
    try:
        return int(raw) if raw is not None else None
    except ValueError:
        return None


def _review_type(raw: str | None) -> str | None:
    return raw if raw in ReviewType.values else None


class ReviewModerationListView(ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = ReviewAdminSerializer

    def get_queryset(self):
        params = self.request.query_params
        return list_reviews_for_admin(
            review_type=_review_type(params.get("type")),
            review_id=_int(params.get("review_id")),
            rating=_rating(params.get("rating")),
            is_hidden=_flag(params.get("is_hidden")),
            ordering=params.get("ordering"),
        )

    @extend_schema(
        parameters=[
            OpenApiParameter("type", str, enum=ReviewType.values),
            OpenApiParameter(
                "review_id",
                int,
                description="A single review, used with type for a link straight to it.",
            ),
            OpenApiParameter("rating", int, description="Exact star rating, 1 to 5."),
            OpenApiParameter("is_hidden", bool),
            OpenApiParameter(
                "ordering",
                str,
                enum=sorted(ADMIN_REVIEW_ORDERING),
                description="Sort column; prefix with - for descending.",
            ),
        ]
    )
    def get(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        rows = [serialize_review(kind, review) for kind, review in hydrate_reviews(page)]
        return self.paginator.get_paginated_response(ReviewAdminSerializer(rows, many=True).data)


class _ReviewModerationView(APIView):
    permission_classes = [IsAdmin]
    review_type: str = ""
    model = None

    def _require(self, review_id: int) -> int:
        if not self.model.objects.filter(pk=review_id).exists():
            raise ResourceNotFoundError("Review not found.")
        return review_id

    def _respond(self, request, *, review_id: int, action: str, message: str) -> Response:
        review = get_review_for_admin(review_type=self.review_type, review_id=review_id)
        # Audit rows are written after the business transaction so a rollback cannot erase them.
        log_request_event(
            request,
            action=action,
            status_code=200,
            details={
                "review_type": self.review_type,
                "review_id": review_id,
                "reason": review.hidden_reason,
            },
        )
        data = serialize_review(self.review_type, review)
        return api_response(
            message=message, request=request, data=ReviewAdminSerializer(data).data
        )

    def _hide(self, request, review_id: int) -> Response:
        self._require(review_id)
        serializer = ReviewReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        hide_review(
            review_type=self.review_type,
            review_id=review_id,
            reason=serializer.validated_data["reason"],
            actor=request.user,
        )
        return self._respond(
            request, review_id=review_id, action=AuditAction.REVIEW_HIDDEN, message="Review hidden."
        )

    def _restore(self, request, review_id: int) -> Response:
        self._require(review_id)
        restore_review(review_type=self.review_type, review_id=review_id)
        return self._respond(
            request,
            review_id=review_id,
            action=AuditAction.REVIEW_RESTORED,
            message="Review restored.",
        )


class FarmerReviewHideView(_ReviewModerationView):
    review_type = ReviewType.FARMER
    model = FarmerReview

    @extend_schema(
        request=ReviewReasonSerializer,
        responses={200: ReviewAdminSerializer, 404: None},
        summary="Hide a farmer review",
    )
    def post(self, request, id: int) -> Response:
        return self._hide(request, id)


class FarmerReviewRestoreView(_ReviewModerationView):
    review_type = ReviewType.FARMER
    model = FarmerReview

    @extend_schema(
        request=None,
        responses={200: ReviewAdminSerializer, 404: None},
        summary="Restore a farmer review",
    )
    def post(self, request, id: int) -> Response:
        return self._restore(request, id)


class ProductReviewHideView(_ReviewModerationView):
    review_type = ReviewType.PRODUCT
    model = ProductReview

    @extend_schema(
        request=ReviewReasonSerializer,
        responses={200: ReviewAdminSerializer, 404: None},
        summary="Hide a product review",
    )
    def post(self, request, id: int) -> Response:
        return self._hide(request, id)


class ProductReviewRestoreView(_ReviewModerationView):
    review_type = ReviewType.PRODUCT
    model = ProductReview

    @extend_schema(
        request=None,
        responses={200: ReviewAdminSerializer, 404: None},
        summary="Restore a product review",
    )
    def post(self, request, id: int) -> Response:
        return self._restore(request, id)
