from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status
from rest_framework.generics import ListAPIView, ListCreateAPIView, RetrieveUpdateDestroyAPIView
from rest_framework.response import Response
from rest_framework.views import APIView

from catalog.admin_portal.serializers_admin import (
    CategoryAdminReadSerializer,
    CategoryAdminWriteSerializer,
    ModerationReasonSerializer,
    ProductAdminSerializer,
    ProductBlockImpactSerializer,
)
from catalog.models import Product
from catalog.selectors import (
    get_product_for_admin,
    list_categories_for_admin,
    list_products_for_admin,
    markets_for_products,
)
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


def _product_context(products) -> dict:
    ids = [product.pk for product in products]
    return {
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
