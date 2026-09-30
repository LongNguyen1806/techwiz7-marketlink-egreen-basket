from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.views.decorators.vary import vary_on_headers
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny

from accounts.public_portal.context import farmer_context
from accounts.public_portal.serializers_public import FarmerSummarySerializer
from accounts.selectors import public_farmers
from favorites.selectors import favorite_ids
from marketlink_core.geo import parse_coordinates
from marketlink_core.responses import api_response
from markets.models import DayOfWeek
from markets.public_portal.serializers_public import MarketSerializer, MarketSummarySerializer
from markets.selectors import order_public_markets, public_market, public_markets

MARKET_PARAMS = [
    OpenApiParameter("q", str, description="Matches the market name or address."),
    OpenApiParameter("day", int, enum=list(DayOfWeek.values), description="ISO weekday, 1 to 7."),
    OpenApiParameter("lat", float),
    OpenApiParameter("lng", float),
    OpenApiParameter("ordering", str, enum=["name", "distance"]),
]


def weekday(raw: str | None) -> int | None:
    try:
        value = int(raw) if raw is not None else None
    except ValueError:
        return None
    return value if value in DayOfWeek.values else None


def market_context(request, markets) -> dict:
    return {
        "favorite_market_ids": favorite_ids(
            user=getattr(request, "user", None),
            kind="market",
            object_ids=[market.pk for market in markets],
        )
    }


@method_decorator(cache_page(60 * 5), name="get")
@method_decorator(vary_on_headers("Authorization"), name="get")
class PublicMarketListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = MarketSummarySerializer

    @extend_schema(parameters=MARKET_PARAMS, responses={200: MarketSummarySerializer(many=True)})
    def get(self, request, *args, **kwargs):
        params = request.query_params
        coordinates = parse_coordinates(params)
        queryset = order_public_markets(
            public_markets(
                q=params.get("q"), day=weekday(params.get("day")), coordinates=coordinates
            ),
            ordering=params.get("ordering"),
            has_coordinates=coordinates is not None,
        )
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True, context=market_context(request, page))
        return self.paginator.get_paginated_response(serializer.data)


class PublicMarketDetailView(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = MarketSerializer
    lookup_url_kwarg = "id"

    def get_queryset(self):
        return public_markets(coordinates=parse_coordinates(self.request.query_params))

    @extend_schema(
        parameters=[OpenApiParameter("lat", float), OpenApiParameter("lng", float)],
        responses={200: MarketSerializer, 404: None},
    )
    def get(self, request, *args, **kwargs):
        market = public_market(
            market_id=kwargs["id"], coordinates=parse_coordinates(request.query_params)
        )
        serializer = MarketSerializer(market, context=market_context(request, [market]))
        return api_response(message="OK", request=request, data=serializer.data)


class PublicMarketFarmerListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = FarmerSummarySerializer

    @extend_schema(
        parameters=[OpenApiParameter("day", int, enum=list(DayOfWeek.values))],
        responses={200: FarmerSummarySerializer(many=True), 404: None},
    )
    def get(self, request, *args, **kwargs):
        market = public_market(market_id=kwargs["id"])
        queryset = public_farmers(market_id=market.pk, day=weekday(request.query_params.get("day")))
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(
            page, many=True, context=farmer_context(request, page, market_id=market.pk)
        )
        return self.paginator.get_paginated_response(serializer.data)

