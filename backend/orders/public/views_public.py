from django.shortcuts import get_object_or_404
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.views import APIView

from accounts.models import FarmerProfile, FarmerStatus
from marketlink_core.responses import api_response
from orders.constants import BOOKING_HORIZON_DAYS
from orders.services.pickup_service import list_pickup_options


MAX_PRODUCT_FILTER = 50


class PickupOptionsQuerySerializer(serializers.Serializer):
    date_from = serializers.DateField(required=False)
    days = serializers.IntegerField(required=False, min_value=1, max_value=BOOKING_HORIZON_DAYS)
    product_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1), required=False, max_length=MAX_PRODUCT_FILTER
    )


class PickupOptionsView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request, farmer_id):
        farmer = get_object_or_404(FarmerProfile, pk=farmer_id, status=FarmerStatus.APPROVED, user__is_active=True)
        raw = {"date_from": request.query_params.get("from"), "days": request.query_params.get("days")}
        products = request.query_params.get("products")
        if products:
            raw["product_ids"] = [part.strip() for part in products.split(",") if part.strip()]
        query = PickupOptionsQuerySerializer(data={key: value for key, value in raw.items() if value is not None})
        query.is_valid(raise_exception=True)
        return api_response(message="OK", data=list_pickup_options(farmer=farmer, **query.validated_data), request=request)
