from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from django.db.models import Q
from django.utils import timezone

from catalog.admin_portal.serializers_admin import (
    AIDecisionSerializer,
    CategoryAdminReadSerializer,
    CategoryAdminWriteSerializer,
    ModerationReasonSerializer,
    PriceGuidelineSerializer,
    ProductAdminSerializer,
    ProductBlockImpactSerializer,
)
from catalog.models import AIAutoAction, AIReviewKind, AIVerdict, PriceGuideline, Product, ProductAIReview
from catalog.selectors import (
    get_product_for_admin,
    list_categories_for_admin,
    list_products_for_admin,
    markets_for_products,
)
from catalog.ai_review.service import review_product
from catalog.ai_review.stats import ai_review_stats
from catalog.services.category_service import delete_category
from catalog.models import ReviewStatus
from catalog.services.product_moderation_service import (
    approve_product,
    block_impact,
    block_product,
    hide_product,
    open_order_counts,
    reject_product,
    restore_product,
    unblock_product,
)
from catalog.services.stock import get_open_held_quantities, get_pending_quantities
from marketlink_core.exceptions import ResourceNotFoundError
from marketlink_core.permissions import IsAdmin
from marketlink_core.responses import api_response
from system.models import AuditAction
from system.services import log_request_event
from catalog.selectors import ADMIN_PRODUCT_ORDERING


class CategoryListCreateView(ListCreateAPIView):
    permission_classes = [IsAdmin]
    pagination_class = None

    def get_queryset(self):
        return list_categories_for_admin()

    def get_serializer_class(self):
        return (
            CategoryAdminWriteSerializer
            if self.request.method == "POST"
            else CategoryAdminReadSerializer
        )

    def list(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_queryset(), many=True)
        return api_response(message="OK", request=request, data=serializer.data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        category = serializer.save()
        return api_response(
            message="Category created.",
            request=request,
            data=CategoryAdminReadSerializer(category).data,
            status_code=201,
        )


class CategoryDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdmin]
    lookup_url_kwarg = "id"
    http_method_names = ["get", "patch", "delete", "head", "options"]

    def get_queryset(self):
        return list_categories_for_admin()

    def get_serializer_class(self):
        return (
            CategoryAdminWriteSerializer
            if self.request.method == "PATCH"
            else CategoryAdminReadSerializer
        )

    def retrieve(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object())
        return api_response(message="OK", request=request, data=serializer.data)

    def update(self, request, *args, **kwargs):
        category = self.get_object()
        serializer = self.get_serializer(category, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        # Re-read through the selector so product_count is annotated again.
        updated = self.get_queryset().get(pk=category.pk)
        return api_response(
            message="Category updated.",
            request=request,
            data=CategoryAdminReadSerializer(updated).data,
        )

    def destroy(self, request, *args, **kwargs):
        delete_category(category_id=self.get_object().pk)
        # 204 carries no body (Pass 4B §2.1), so this one response skips the envelope.
        return Response(status=status.HTTP_204_NO_CONTENT)


# How many cancelled order ids one audit row will carry. Beyond this the list stops being
# something a person reads and the JSON column starts paying for it.
AUDIT_ID_LIMIT = 200


def _flag(raw: str | None) -> bool | None:
    if raw is None:
        return None
    lowered = raw.strip().lower()
    if lowered in ("true", "1"):
        return True
    if lowered in ("false", "0"):
        return False
    return None


def _int(raw: str | None) -> int | None:
    try:
        return int(raw) if raw is not None else None
    except ValueError:
        return None


def _latest_reviews(ids: list[int], kind: str) -> dict[int, ProductAIReview]:
    """The newest review of each kind per product, in one query for the whole page."""
    latest: dict[int, ProductAIReview] = {}
    reviews = (
        ProductAIReview.objects.filter(product_id__in=ids, kind=kind)
        .select_related("suggested_category")
        .order_by("product_id", "-created_at", "-id")
    )
    for review in reviews:
        latest.setdefault(review.product_id, review)
    return latest


def _product_context(products) -> dict:
    ids = [product.pk for product in products]
    return {
        "ai_reviews": _latest_reviews(ids, AIReviewKind.LISTING),
        "ai_photo_checks": _latest_reviews(ids, AIReviewKind.WEEKLY_IMAGE),
        "held_quantities": get_open_held_quantities(product_ids=ids),
        "pending_quantities": get_pending_quantities(product_ids=ids),
        "markets": markets_for_products(product_ids=ids),
        # What a block would cancel, shown on the row so the admin sees the cost before
        # opening the dialog.
        "open_order_counts": open_order_counts(product_ids=ids),
    }


class ProductModerationListView(ListAPIView):
    permission_classes = [IsAdmin]
    serializer_class = ProductAdminSerializer

    def get_queryset(self):
        params = self.request.query_params
        return list_products_for_admin(
            q=params.get("q"),
            farmer_id=_int(params.get("farmer_id")),
            product_id=_int(params.get("product_id")),
            category_id=_int(params.get("category_id")),
            is_hidden=_flag(params.get("is_hidden")),
            review_status=params.get("review_status"),
            ai_verdict=params.get("ai_verdict"),
            ordering=params.get("ordering"),
        )

    @extend_schema(
        parameters=[
            OpenApiParameter("q", str, description="Matches the product name or stall name."),
            OpenApiParameter("farmer_id", int),
            OpenApiParameter(
                "product_id", int, description="A single product, for a link straight to it."
            ),
            OpenApiParameter("category_id", int),
            OpenApiParameter("is_hidden", bool),
            OpenApiParameter("review_status", str, enum=[*ReviewStatus.values]),
            OpenApiParameter(
                "ai_verdict",
                str,
                enum=[*AIVerdict.values, "NONE"],
                description="Latest AI listing review; NONE = not reviewed yet.",
            ),
            OpenApiParameter(
                "ordering",
                str,
                enum=sorted(ADMIN_PRODUCT_ORDERING),
                description="Sort column; prefix with - for descending.",
            ),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)

    def list(self, request, *args, **kwargs):
        page = self.paginate_queryset(self.get_queryset())
        serializer = self.get_serializer(page, many=True, context=_product_context(page))
        return self.paginator.get_paginated_response(serializer.data)


class _ProductModerationView(APIView):
    permission_classes = [IsAdmin]

    def _respond(
        self,
        request,
        *,
        product_id: int,
        action: str,
        message: str,
        extra: dict | None = None,
        audit_extra: dict | None = None,
    ) -> Response:
        product = get_product_for_admin(product_id=product_id)
        # Audit rows are written after the business transaction so a rollback cannot erase them.
        log_request_event(
            request,
            action=action,
            status_code=200,
            details={
                "product_id": product_id,
                "reason": product.hidden_reason or product.review_note,
                **(extra or {}),
                **(audit_extra or {}),
            },
        )
        serializer = ProductAdminSerializer(product, context=_product_context([product]))
        return api_response(
            message=message, request=request, data={**serializer.data, **(extra or {})}
        )


class ProductHideView(_ProductModerationView):
    @extend_schema(
        request=ModerationReasonSerializer,
        responses={200: ProductAdminSerializer, 404: None},
        summary="Hide a product",
    )
    def post(self, request, id: int) -> Response:
        _require_product(id)
        serializer = ModerationReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        hide_product(
            product_id=id, reason=serializer.validated_data["reason"], actor=request.user
        )
        return self._respond(
            request,
            product_id=id,
            action=AuditAction.PRODUCT_HIDDEN,
            message="Product hidden.",
        )


class ProductRestoreView(_ProductModerationView):
    @extend_schema(
        request=None, responses={200: ProductAdminSerializer, 404: None}, summary="Restore a product"
    )
    def post(self, request, id: int) -> Response:
        _require_product(id)
        restore_product(product_id=id)
        return self._respond(
            request,
            product_id=id,
            action=AuditAction.PRODUCT_RESTORED,
            message="Product restored.",
        )


class ProductBlockImpactView(APIView):
    permission_classes = [IsAdmin]

    @extend_schema(
        responses={200: ProductBlockImpactSerializer, 404: None},
        summary="What blocking this product would cancel",
    )
    def get(self, request, id: int) -> Response:
        _require_product(id)
        return api_response(
            message="OK", request=request, data=block_impact(product_id=id)
        )


class ProductBlockView(_ProductModerationView):
    @extend_schema(
        request=ModerationReasonSerializer,
        responses={200: ProductAdminSerializer, 404: None},
        summary="Block a product and cancel its open orders",
    )
    def post(self, request, id: int) -> Response:
        _require_product(id)
        serializer = ModerationReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _, cancelled = block_product(
            product_id=id, reason=serializer.validated_data["reason"], actor=request.user
        )
        return self._respond(
            request,
            product_id=id,
            action=AuditAction.PRODUCT_BLOCKED,
            message="Product blocked.",
            extra={"affected_orders": len(cancelled)},
            # Which orders, not just how many. The count says the takedown was costly; the
            # ids are what lets someone answer a shopper asking why theirs disappeared.
            # Capped so one enormous takedown cannot bloat the log row.
            audit_extra={
                "cancelled_order_ids": cancelled[:AUDIT_ID_LIMIT],
                **(
                    {"cancelled_order_ids_truncated": True}
                    if len(cancelled) > AUDIT_ID_LIMIT
                    else {}
                ),
            },
        )


class ProductUnblockView(_ProductModerationView):
    @extend_schema(
        request=None,
        responses={200: ProductAdminSerializer, 404: None},
        summary="Put a blocked product back on sale",
    )
    def post(self, request, id: int) -> Response:
        _require_product(id)
        unblock_product(product_id=id)
        # Deliberately not "restored": the cancelled orders stay cancelled, and the message
        # should not suggest otherwise.
        return self._respond(
            request,
            product_id=id,
            action=AuditAction.PRODUCT_UNBLOCKED,
            message="Product is on sale again. The cancelled orders were not reinstated.",
        )


class ProductApproveView(_ProductModerationView):
    @extend_schema(
        request=None,
        responses={200: ProductAdminSerializer, 404: None},
        summary="Approve a listing so shoppers can see it",
    )
    def post(self, request, id: int) -> Response:
        _require_product(id)
        approve_product(product_id=id, actor=request.user)
        return self._respond(
            request,
            product_id=id,
            action=AuditAction.PRODUCT_APPROVED,
            message="Listing approved.",
        )


class ProductRejectView(_ProductModerationView):
    @extend_schema(
        request=ModerationReasonSerializer,
        responses={200: ProductAdminSerializer, 404: None},
        summary="Refuse a listing, with a reason the stall can act on",
    )
    def post(self, request, id: int) -> Response:
        _require_product(id)
        serializer = ModerationReasonSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        reject_product(
            product_id=id, reason=serializer.validated_data["reason"], actor=request.user
        )
        return self._respond(
            request,
            product_id=id,
            action=AuditAction.PRODUCT_REJECTED,
            message="Listing refused. The stall has been told why.",
        )


def _require_product(product_id: int) -> int:
    if not Product.objects.filter(pk=product_id).exists():
        raise ResourceNotFoundError("Product not found.")
    return product_id


# ------------------------------------------------------------------ AI-assisted listing review


class ProductAIRecheckView(APIView):
    """Run the AI review again now (after a guideline change, or when it was unavailable)."""

    permission_classes = [IsAdmin]

    @extend_schema(request=None, responses={200: ProductAdminSerializer, 404: None}, summary="Re-run the AI listing review")
    def post(self, request, id: int) -> Response:
        _require_product(id)
        review_product(id, force=True)
        product = list_products_for_admin(product_id=id).first()
        data = ProductAdminSerializer(product, context=_product_context([product])).data
        return api_response(message="AI review finished. It is advice; the decision stays yours.", data=data, request=request)


class PriceGuidelineListCreateView(ListCreateAPIView):
    permission_classes = [IsAdmin]
    serializer_class = PriceGuidelineSerializer
    pagination_class = None
    queryset = PriceGuideline.objects.select_related("category")

    def list(self, request, *args, **kwargs):
        return api_response(message="OK", data=self.get_serializer(self.get_queryset(), many=True).data, request=request)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return api_response(message="Guideline added.", data=serializer.data, status_code=status.HTTP_201_CREATED, request=request)


class PriceGuidelineDetailView(RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAdmin]
    serializer_class = PriceGuidelineSerializer
    queryset = PriceGuideline.objects.select_related("category")
    lookup_url_kwarg = "id"
    http_method_names = ["get", "patch", "delete"]

    def retrieve(self, request, *args, **kwargs):
        return api_response(message="OK", data=self.get_serializer(self.get_object()).data, request=request)

    def update(self, request, *args, **kwargs):
        serializer = self.get_serializer(self.get_object(), data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return api_response(message="Guideline saved.", data=serializer.data, request=request)

    def destroy(self, request, *args, **kwargs):
        self.get_object().delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class AIReviewStatsView(APIView):
    """How the AI's advice compares with what admins then decided."""

    permission_classes = [IsAdmin]

    @extend_schema(parameters=[OpenApiParameter("days", int, description="Look-back window, 1-365 (default 30).")])
    def get(self, request) -> Response:
        return api_response(message="OK", data=ai_review_stats(days=_int(request.query_params.get("days")) or 30), request=request)


class AIDecisionListView(ListAPIView):
    """#8: what the AI approved or held on its own, newest first, unchecked by default."""

    permission_classes = [IsAdmin]
    serializer_class = AIDecisionSerializer

    def get_queryset(self):
        params = self.request.query_params
        rows = (
            ProductAIReview.objects.filter(auto_action__isnull=False)
            .select_related("product__farmer", "product__category", "admin_checked_by")
            .order_by("-auto_action_at", "-id")
        )
        action = params.get("action")
        if action in AIAutoAction.values:
            rows = rows.filter(auto_action=action)
        checked = (params.get("checked") or "false").lower()
        if checked in ("true", "false"):
            rows = rows.filter(admin_checked_at__isnull=checked == "false")
        q = (params.get("q") or "").strip()
        if q:
            rows = rows.filter(Q(product__name__icontains=q) | Q(product__farmer__stall_name__icontains=q))
        return rows

    @extend_schema(
        parameters=[
            OpenApiParameter("action", str, enum=[*AIAutoAction.values]),
            OpenApiParameter("checked", str, enum=["true", "false", "all"], description="Default false."),
            OpenApiParameter("q", str, description="Product or stall name."),
        ]
    )
    def get(self, request, *args, **kwargs):
        return super().get(request, *args, **kwargs)


class AIDecisionCheckView(APIView):
    """#8: the admin looked at an AI decision and lets it stand."""

    permission_classes = [IsAdmin]

    @extend_schema(request=None, responses={200: AIDecisionSerializer, 404: None})
    def post(self, request, id: int) -> Response:
        review = (
            ProductAIReview.objects.select_related("product__farmer", "product__category")
            .filter(pk=id, auto_action__isnull=False)
            .first()
        )
        if review is None:
            raise ResourceNotFoundError("AI decision not found.")
        if review.admin_checked_at is None:
            review.admin_checked_at, review.admin_checked_by = timezone.now(), request.user
            review.save(update_fields=["admin_checked_at", "admin_checked_by"])
        return api_response(message="Marked as checked.", request=request, data=AIDecisionSerializer(review).data)
