from decimal import Decimal, InvalidOperation

from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny

from catalog.public_portal.serializers_public import (
    CategoryPublicSerializer,
    ProductCardSerializer,
    ProductDetailSerializer,
)
from catalog.selectors import (
    MAX_CART_REFRESH_IDS,
    list_active_categories,
    markets_for_products,
    public_product,
    public_products,
)
from favorites.selectors import favorite_ids
from marketlink_core.responses import api_response
from markets.models import DayOfWeek

PRODUCT_ORDERINGS = ["newest", "price_asc", "price_desc", "rating"]
PRODUCT_PARAMS = [
    OpenApiParameter("q", str, description="Matches the product name or stall name."),
    OpenApiParameter("category", str, description="Comma-separated category ids."),
    OpenApiParameter("market_id", int),
    OpenApiParameter("day", int, enum=list(DayOfWeek.values)),
    OpenApiParameter("farmer_id", int),
    OpenApiParameter("price_min", float),
    OpenApiParameter("price_max", float),
    OpenApiParameter("in_stock", bool, description="Defaults to true."),
    OpenApiParameter(
        "ids",
        str,
        description=(
            f"Comma-separated ids, at most {MAX_CART_REFRESH_IDS}. Refreshing the cart also "
            "returns paused and sold-out rows so they can be marked Unavailable."
        ),
    ),
    OpenApiParameter("ordering", str, enum=PRODUCT_ORDERINGS),
]


def int_list(raw: str | None) -> list[int]:
    if not raw:
        return []
    values = []
    for chunk in raw.split(","):
        try:
            values.append(int(chunk.strip()))
        except ValueError:
            continue
    return values


def optional_int(raw: str | None) -> int | None:
    try:
        return int(raw) if raw is not None else None
    except ValueError:
        return None


def optional_decimal(raw: str | None) -> Decimal | None:
    try:
        return Decimal(str(raw)) if raw is not None else None
    except (InvalidOperation, ValueError):
        return None


def weekday(raw: str | None) -> int | None:
    value = optional_int(raw)
    return value if value in DayOfWeek.values else None


def in_stock_flag(raw: str | None) -> bool:
    return raw is None or raw.strip().lower() not in ("false", "0")


def product_context(request, products, *, with_markets: bool = False) -> dict:
    ids = [product.pk for product in products]
    context = {
        "favorite_product_ids": favorite_ids(
            user=getattr(request, "user", None), kind="product", object_ids=ids
        )
    }
    if with_markets:
        context["markets"] = markets_for_products(product_ids=ids)
    return context


class PublicCategoryListView(ListAPIView):
    permission_classes = [AllowAny]
    pagination_class = None
    serializer_class = CategoryPublicSerializer

    @extend_schema(responses={200: CategoryPublicSerializer(many=True)})
    def get(self, request, *args, **kwargs):
        serializer = self.get_serializer(list_active_categories(), many=True)
        return api_response(message="OK", request=request, data=serializer.data)


class PublicProductListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductCardSerializer

    @extend_schema(parameters=PRODUCT_PARAMS, responses={200: ProductCardSerializer(many=True)})
    def get(self, request, *args, **kwargs):
        params = request.query_params
        queryset = public_products(
            q=params.get("q"),
            category_ids=int_list(params.get("category")),
            market_id=optional_int(params.get("market_id")),
            day=weekday(params.get("day")),
            farmer_id=optional_int(params.get("farmer_id")),
            price_min=optional_decimal(params.get("price_min")),
            price_max=optional_decimal(params.get("price_max")),
            in_stock=in_stock_flag(params.get("in_stock")),
            ids=int_list(params.get("ids")),
            ordering=params.get("ordering"),
        )
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True, context=product_context(request, page))
        return self.paginator.get_paginated_response(serializer.data)


class PublicProductDetailView(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = ProductDetailSerializer
    lookup_url_kwarg = "id"

    def get_queryset(self):
        return public_products(in_stock=False)

    @extend_schema(responses={200: ProductDetailSerializer, 404: None})
    def get(self, request, *args, **kwargs):
        product = public_product(product_id=kwargs["id"])
        serializer = ProductDetailSerializer(
            product, context=product_context(request, [product], with_markets=True)
        )
        return api_response(message="OK", request=request, data=serializer.data)
