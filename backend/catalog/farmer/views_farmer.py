from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Count, Q
from rest_framework import status
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import FarmerProfile, FarmerStatus
from catalog.ai_review.rules import run_rules
from catalog.ai_review.types import ListingInput, verdict_for
from catalog.farmer.serializers_farmer import (
    FarmerProductBulkSerializer,
    FarmerProductCreateSerializer,
    FarmerProductPrecheckSerializer,
    FarmerProductSerializer,
    FarmerProductUpdateSerializer,
    order_window_error,
)
from catalog.models import Category, Product, ReviewStatus
from catalog.services.farmer_product import (
    apply_weekly_template,
    build_product_metrics,
    notify_restock_for_product,
    preview_weekly_template,
    sell_everywhere,
    set_product_markets,
    validate_market_ids,
)
from catalog.ai_review.service import close_ai_flags, schedule_listing_review
from catalog.services.product_moderation_service import needs_review_again, send_back_for_review
from marketlink_core.exceptions import (
    BusinessValidationError,
    ErrorCode,
    ForbiddenActionError,
    ResourceNotFoundError,
    UnprocessableEntityError,
)
from marketlink_core.history import save_with_history
from marketlink_core.pagination import StandardPagination
from marketlink_core.permissions import IsFarmer
from marketlink_core.responses import api_response
from markets.models import FarmerMarket
from orders.farmer.serializers_farmer import FarmerOrderSummarySerializer
from orders.services.fsm import run_with_retry_if_top_level

PRODUCT_STATES = ("in_stock", "out_of_stock", "unavailable", "hidden", "archived", "in_review", "rejected")
# Fields FA-14 may change; the save lists exactly the changed ones (never a full-row write).
UPDATABLE_FIELDS = (
    "name",
    "price",
    "unit",
    "stock_quantity",
    "weekly_default_quantity",
    "min_per_order",
    "max_per_order",
    "description",
    "image",
    "is_available",
)


def _reviewable_changes(product: Product, before: dict[str, Any], had_image: bool, validated: dict) -> list[str]:
    """REVIEWABLE_FIELDS whose value really changed. The form resends every field on save, so
    "present in the body" is not "changed"; a re-sent name must not send the listing back."""
    changed = [field for field, old in before.items() if getattr(product, field) != old]
    # A new file is always a new image; a null only counts when there was one to remove.
    if "image" in validated and (validated["image"] or had_image):
        changed.append("image")
    return changed


ACTIVE = Q(is_archived=False)
STATE_FILTERS = {
    "in_stock": Q(
        is_archived=False,
        is_hidden_by_admin=False,
        is_available=True,
        stock_quantity__gt=0,
        review_status=ReviewStatus.APPROVED,
    ),
    "out_of_stock": Q(is_archived=False, is_hidden_by_admin=False, stock_quantity=0),
    "unavailable": Q(is_archived=False, is_available=False),
    "hidden": Q(is_hidden_by_admin=True),
    "archived": Q(is_archived=True),
    "in_review": Q(is_archived=False, review_status=ReviewStatus.PENDING),
    "rejected": Q(is_archived=False, review_status=ReviewStatus.REJECTED),
}


def _positive_int(raw: str | None, field: str, errors: dict[str, list[str]]) -> int | None:
    if raw in (None, ""):
        return None
    if not raw.isdigit() or int(raw) < 1:
        errors[field] = ["Must be a positive integer."]
        return None
    return int(raw)


def _parse_list_filters(params) -> dict[str, Any]:
    errors: dict[str, list[str]] = {}
    category_id = _positive_int(params.get("category_id"), "category_id", errors)
    market_id = _positive_int(params.get("market_id"), "market_id", errors)
    state = params.get("state") or None
    if state and state not in PRODUCT_STATES:
        errors["state"] = [f"Use one of: {', '.join(PRODUCT_STATES)}."]
    if errors:
        raise BusinessValidationError(
            "Invalid query parameters.", code=ErrorCode.VALIDATION_ERROR, errors=errors
        )
    return {
        "q": params.get("q", "").strip(),
        "category_id": category_id,
        "market_id": market_id,
        "state": state,
    }


def _farmer_products(profile: FarmerProfile, filters: dict[str, Any]):
    qs = Product.objects.filter(farmer=profile).select_related("category", "farmer")
    if filters["q"]:
        qs = qs.filter(Q(name__icontains=filters["q"]) | Q(description__icontains=filters["q"]))
    if filters["category_id"] is not None:
        qs = qs.filter(category_id=filters["category_id"])
    if filters["market_id"] is not None:
        stall = FarmerMarket.objects.filter(farmer=profile, market_id=filters["market_id"]).first()
        if stall is None:
            return qs.none()
        qs = qs.filter(market_links__farmer_market_id=stall.pk)
    return qs


class FarmerBaseProductView(APIView):
    permission_classes = [IsFarmer]

    def _get_farmer_profile(self, request: Request) -> FarmerProfile:
        profile = getattr(request.user, "farmer_profile", None)
        if not profile:
            raise ResourceNotFoundError("Farmer profile not found.", code=ErrorCode.NOT_FOUND)
        return profile

    def _check_can_write(self, profile: FarmerProfile, *, require_approved: bool) -> None:
        # Pass 4B §5.4: every write endpoint of a suspended farmer returns FARMER_SUSPENDED.
        if profile.status == FarmerStatus.SUSPENDED:
            raise ForbiddenActionError(
                "Your stall is suspended, so products cannot be changed.",
                code=ErrorCode.FARMER_SUSPENDED,
            )
        if require_approved and profile.status != FarmerStatus.APPROVED:
            raise ForbiddenActionError(
                "Only approved farmers can perform this action.",
                code=ErrorCode.FARMER_NOT_APPROVED,
            )

    def _check_farmer_approved(self, profile: FarmerProfile) -> None:
        if profile.status != FarmerStatus.APPROVED:
            raise ForbiddenActionError(
                "Only approved farmers can perform this action.",
                code=ErrorCode.FARMER_NOT_APPROVED,
            )

    def _get_farmer_product(self, profile: FarmerProfile, pk: int, *, lock: bool = False) -> Product:
        qs = Product.objects.filter(pk=pk, farmer=profile)
        if lock:
            qs = qs.select_for_update(of=("self",))
        product = qs.first()
        if not product:
            raise ResourceNotFoundError("Product not found.", code=ErrorCode.NOT_FOUND)
        return product

    def _product_data(self, request: Request, profile: FarmerProfile, product: Product) -> dict[str, Any]:
        metrics = build_product_metrics(farmer=profile, product_ids=[product.id])
        return FarmerProductSerializer(
            product, context={"request": request, "product_metrics": metrics}
        ).data


class FarmerProductListView(FarmerBaseProductView):
    pagination_class = StandardPagination

    def get(self, request: Request) -> Response:
        """FA-11: list the farmer's products with search, category and state filters."""
        profile = self._get_farmer_profile(request)
        filters = _parse_list_filters(request.query_params)
        qs = _farmer_products(profile, filters).filter(STATE_FILTERS.get(filters["state"], ACTIVE))

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs.order_by("-created_at", "-id"), request)
        metrics = build_product_metrics(farmer=profile, product_ids=[p.id for p in page])
        serializer = FarmerProductSerializer(
            page, many=True, context={"request": request, "product_metrics": metrics}
        )
        return paginator.get_paginated_response(serializer.data)

    def post(self, request: Request) -> Response:
        """FA-12: create a product (APPROVED farmer only)."""
        profile = self._get_farmer_profile(request)
        self._check_can_write(profile, require_approved=True)
        if not FarmerMarket.objects.selling().filter(farmer=profile).exists():
            raise UnprocessableEntityError(
                "You can list products once a market has approved your stall.",
                code=ErrorCode.FAILED_PRECONDITION,
            )

        serializer = FarmerProductCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data
        market_ids = validated.get("market_ids")
        if market_ids is not None:
            validate_market_ids(farmer=profile, market_ids=market_ids)

        with transaction.atomic():
            product = Product.objects.create(
                farmer=profile,
                category=Category.objects.get(id=validated["category_id"]),
                name=validated["name"].strip(),
                price=validated["price"],
                unit=validated["unit"],
                stock_quantity=validated["stock_quantity"],
                weekly_default_quantity=validated.get("weekly_default_quantity"),
                min_per_order=validated.get("min_per_order", 1),
                max_per_order=validated.get("max_per_order"),
                description=validated.get("description"),
                image=validated.get("image"),
                is_available=validated.get("is_available", True),
            )
            if market_ids is not None:
                set_product_markets(product=product, market_ids=market_ids)
            else:
                sell_everywhere(product=product)
            # New listings start PENDING; the AI advises the admin in the background.
            schedule_listing_review(product.pk)
        return api_response(
            message="Product created successfully.",
            data=self._product_data(request, profile, product),
            status_code=status.HTTP_201_CREATED,
            request=request,
        )


class FarmerProductDetailView(FarmerBaseProductView):
    def get(self, request: Request, pk: int) -> Response:
        """FA-13."""
        profile = self._get_farmer_profile(request)
        product = self._get_farmer_product(profile, pk)
        return api_response(message="OK", data=self._product_data(request, profile, product), request=request)

    def patch(self, request: Request, pk: int) -> Response:
        """FA-14: partial update under a row lock; restock alert when stock goes 0 -> > 0 (D-025)."""
        profile = self._get_farmer_profile(request)
        self._check_can_write(profile, require_approved=True)
        self._get_farmer_product(profile, pk)  # 404 before validating the body

        serializer = FarmerProductUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data
        category = Category.objects.get(id=validated["category_id"]) if "category_id" in validated else None

        def _execute() -> tuple[Product, int]:
            with transaction.atomic():
                # Lock first so a concurrent accept (T2) cannot be overwritten by a stale row.
                product = self._get_farmer_product(profile, pk, lock=True)
                if product.is_archived or product.is_hidden_by_admin:
                    raise UnprocessableEntityError(
                        "Cannot modify an archived or admin-hidden product.",
                        code=ErrorCode.FAILED_PRECONDITION,
                    )
                old_stock = product.stock_quantity
                before = {"name": product.name, "description": product.description, "category_id": product.category_id}
                had_image = bool(product.image)
                changed: list[str] = []
                if category is not None:
                    product.category = category
                    changed.append("category")
                for field in UPDATABLE_FIELDS:
                    if field in validated:
                        value = validated[field]
                        setattr(product, field, value.strip() if field == "name" else value)
                        changed.append(field)
                # Either end may change alone, so the pair is checked against the resulting row.
                window_error = order_window_error(product.min_per_order, product.max_per_order)
                if window_error:
                    raise BusinessValidationError(
                        window_error, code=ErrorCode.VALIDATION_ERROR, errors={"min_per_order": [window_error]}
                    )
                if changed:
                    product.save(update_fields=[*changed, "updated_at"])
                if "market_ids" in validated:
                    set_product_markets(product=product, market_ids=validated["market_ids"])

                # Changing what the listing is (name, description, image, category) takes it off
                # the shopper side until an admin approves it again; open orders keep going.
                sent_back = needs_review_again(product, _reviewable_changes(product, before, had_image, validated))
                if sent_back:
                    send_back_for_review(product)
                if product.review_status == ReviewStatus.PENDING:
                    # Unchanged content is not reviewed twice (content hash), so this is cheap.
                    schedule_listing_review(product.pk)

                restock_notified = 0
                if old_stock == 0 and product.stock_quantity > 0 and product.is_available:
                    restock_notified = notify_restock_for_product(product=product)
            return product, restock_notified, sent_back

        product, restock_notified, sent_back = run_with_retry_if_top_level(_execute)
        data = self._product_data(request, profile, product)
        data["restock_notified"] = restock_notified
        data["sent_for_review"] = sent_back
        message = (
            "Product updated. Shoppers will see it again once an administrator approves the changes."
            if sent_back
            else "Product updated successfully."
        )
        return api_response(message=message, data=data, request=request)

    def delete(self, request: Request, pk: int) -> Response:
        """FA-15: soft delete (is_archived = True, D-017)."""
        profile = self._get_farmer_profile(request)
        self._check_can_write(profile, require_approved=False)
        product = self._get_farmer_product(profile, pk)
        product.is_archived = True
        save_with_history(product, update_fields=["is_archived", "updated_at"], reason="Archived by farmer")
        # An archived listing is off sale for good; the AI's question about it no longer needs an answer.
        close_ai_flags(product.pk, resolution="Listing archived by the stall.")
        return Response(status=status.HTTP_204_NO_CONTENT)


class FarmerProductMarkSoldOutView(FarmerBaseProductView):
    def post(self, request: Request, pk: int) -> Response:
        """FA-16: quick mark as sold out (stock_quantity = 0) under a row lock."""
        profile = self._get_farmer_profile(request)
        self._check_can_write(profile, require_approved=False)

        def _execute() -> Product:
            with transaction.atomic():
                product = self._get_farmer_product(profile, pk, lock=True)
                if product.stock_quantity != 0:
                    product.stock_quantity = 0
                    save_with_history(
                        product, update_fields=["stock_quantity", "updated_at"], reason="Marked sold out by farmer"
                    )
            return product

        product = run_with_retry_if_top_level(_execute)
        return api_response(message="OK", data=self._product_data(request, profile, product), request=request)


class FarmerProductCountsView(FarmerBaseProductView):
    def get(self, request: Request) -> Response:
        profile = self._get_farmer_profile(request)
        filters = _parse_list_filters(request.query_params)
        counts = _farmer_products(profile, filters).aggregate(
            all=Count("id", filter=ACTIVE),
            **{state: Count("id", filter=condition) for state, condition in STATE_FILTERS.items()},
        )
        return api_response(message="OK", data=counts, request=request)


BULK_MESSAGES = {
    "sold_out": "Marked sold out.",
    "pause": "Paused.",
    "resume": "Open for sale again.",
    "set_markets": "Markets updated.",
}


class FarmerProductBulkView(FarmerBaseProductView):
    def post(self, request: Request) -> Response:
        profile = self._get_farmer_profile(request)
        serializer = FarmerProductBulkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        action = serializer.validated_data["action"]
        product_ids = serializer.validated_data["product_ids"]
        market_ids = serializer.validated_data.get("market_ids")
        self._check_can_write(profile, require_approved=action != "sold_out")
        if action == "set_markets":
            validate_market_ids(farmer=profile, market_ids=market_ids)

        def _execute() -> int:
            with transaction.atomic():
                products = list(
                    Product.objects.select_for_update(of=("self",))
                    .select_related("farmer")
                    .filter(farmer=profile, pk__in=product_ids, is_archived=False)
                    .order_by("id")
                )
                updated = 0
                for product in products:
                    if action == "sold_out":
                        if product.stock_quantity == 0:
                            continue
                        product.stock_quantity = 0
                        save_with_history(
                            product, update_fields=["stock_quantity", "updated_at"], reason="Marked sold out by farmer"
                        )
                    elif product.is_hidden_by_admin:
                        continue
                    elif action in ("pause", "resume"):
                        open_for_sale = action == "resume"
                        if product.is_available == open_for_sale:
                            continue
                        product.is_available = open_for_sale
                        save_with_history(
                            product,
                            update_fields=["is_available", "updated_at"],
                            reason="Opened for sale by farmer" if open_for_sale else "Paused by farmer",
                        )
                    else:
                        set_product_markets(product=product, market_ids=market_ids)
                    updated += 1
                return updated

        updated = run_with_retry_if_top_level(_execute)
        return api_response(message=BULK_MESSAGES[action], data={"updated": updated}, request=request)


class FarmerWeeklyTemplatePreviewView(FarmerBaseProductView):
    def get(self, request: Request) -> Response:
        """FA-17: preview weekly stock template calculation (Farmer APPROVED required)."""
        profile = self._get_farmer_profile(request)
        self._check_farmer_approved(profile)

        preview = preview_weekly_template(farmer=profile)
        data = {
            "rows": preview["rows"],
            # OrderSummary gives the dialog the version needed for If-Match on Complete / No-show.
            "overdue_orders": FarmerOrderSummarySerializer(
                preview["overdue_orders"], many=True, context={"request": request}
            ).data,
        }
        return api_response(message="OK", data=data, request=request)


class FarmerWeeklyTemplateApplyView(FarmerBaseProductView):
    def post(self, request: Request) -> Response:
        """FA-18: apply weekly stock template with row-locking (Farmer APPROVED required)."""
        profile = self._get_farmer_profile(request)
        self._check_can_write(profile, require_approved=True)

        apply_data = apply_weekly_template(farmer=profile)
        return api_response(message="OK", data=apply_data, request=request)


class FarmerProductPrecheckView(FarmerBaseProductView):
    """Rule checks on the product form as the farmer types (no AI, nothing saved).

    Advice only: the farmer can still save; an administrator reviews every listing anyway.
    """

    def get(self, request: Request) -> Response:
        profile = self._get_farmer_profile(request)
        serializer = FarmerProductPrecheckSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        category = Category.objects.filter(pk=data.get("category_id")).first()
        product_id = data.get("product_id")
        if product_id and not Product.objects.filter(pk=product_id, farmer=profile).exists():
            product_id = None
        listing = ListingInput(
            name=data.get("name", ""),
            description=data.get("description", ""),
            category_id=category.pk if category else None,
            category_name=category.name if category else "",
            unit=data.get("unit", "KG"),
            price=data.get("price", Decimal("0.01")),
            stock_quantity=data.get("stock_quantity", 0),
            min_per_order=data.get("min_per_order", 1),
            max_per_order=data.get("max_per_order"),
            product_id=product_id,
        )
        findings = run_rules(listing)
        return api_response(
            message="OK",
            data={"findings": [finding.as_dict() for finding in findings], "verdict": verdict_for(findings)},
            request=request,
        )
