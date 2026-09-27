from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import serializers
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.permissions import AllowAny
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from accounts.geocoding import geocode_address

from accounts.public_portal.context import farmer_context
from accounts.public_portal.serializers_public import (
    FarmerPublicSerializer,
    FarmerSummarySerializer,
)
from accounts.selectors import pickup_windows, public_farmer, public_farmers
from marketlink_core.geo import parse_coordinates
from marketlink_core.responses import api_response
from markets.models import DayOfWeek

FARMER_ORDERINGS = ["rating", "in_stock", "distance", "name"]
FARMER_PARAMS = [
    OpenApiParameter("q", str, description="Matches the stall name or the market it trades at."),
    OpenApiParameter("market_id", int),
    OpenApiParameter("day", int, enum=list(DayOfWeek.values)),
    OpenApiParameter("category_id", int),
    OpenApiParameter("lat", float),
    OpenApiParameter("lng", float),
    OpenApiParameter("ordering", str, enum=FARMER_ORDERINGS),
]


def optional_int(raw: str | None) -> int | None:
    try:
        return int(raw) if raw is not None else None
    except ValueError:
        return None


def weekday(raw: str | None) -> int | None:
    value = optional_int(raw)
    return value if value in DayOfWeek.values else None


class PublicFarmerListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = FarmerSummarySerializer

    @extend_schema(parameters=FARMER_PARAMS, responses={200: FarmerSummarySerializer(many=True)})
    def get(self, request, *args, **kwargs):
        params = request.query_params
        queryset = public_farmers(
            q=params.get("q"),
            market_id=optional_int(params.get("market_id")),
            day=weekday(params.get("day")),
            category_id=optional_int(params.get("category_id")),
            coordinates=parse_coordinates(params),
            ordering=params.get("ordering"),
        )
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True, context=farmer_context(request, page))
        return self.paginator.get_paginated_response(serializer.data)


class PublicFarmerDetailView(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = FarmerPublicSerializer
    lookup_url_kwarg = "id"

    def get_queryset(self):
        return public_farmers()

    @extend_schema(responses={200: FarmerPublicSerializer, 404: None})
    def get(self, request, *args, **kwargs):
        farmer = public_farmer(farmer_id=kwargs["id"])
        context = farmer_context(request, [farmer])
        context["pickup_windows"] = pickup_windows(farmer_id=farmer.pk)
        serializer = FarmerPublicSerializer(farmer, context=context)
        return api_response(message="OK", request=request, data=serializer.data)


class GeocodeQuerySerializer(serializers.Serializer):
    q = serializers.CharField(min_length=5, max_length=255)


class GeocodeResultSerializer(serializers.Serializer):
    found = serializers.BooleanField()
    latitude = serializers.FloatField(allow_null=True)
    longitude = serializers.FloatField(allow_null=True)


class GeocodeView(APIView):
    """Place an address on the map (sign-up map, admin market form).

    Open to guests because the sign-up form needs it, so it has its own throttle on top of the
    app-wide one request per second Nominatim allows. Only the full address is searched:
    trimmed-down searches were tried and put pins kilometres away, which is worse than no pin.
    The result is only a starting point; the person always sees the pin and can move it.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "geocode"

    @extend_schema(
        parameters=[OpenApiParameter("q", str, required=True, description="The address to look up.")],
        responses={200: GeocodeResultSerializer},
        summary="Look up an address on the map",
    )
    def get(self, request):
        query = GeocodeQuerySerializer(data=request.query_params)
        query.is_valid(raise_exception=True)
        coordinates = geocode_address(query.validated_data["q"])
        data = {
            "found": coordinates is not None,
            "latitude": float(coordinates[0]) if coordinates else None,
            "longitude": float(coordinates[1]) if coordinates else None,
        }
        return api_response(message="OK", request=request, data=data)
