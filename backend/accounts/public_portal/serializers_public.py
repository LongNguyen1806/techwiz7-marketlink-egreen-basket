from rest_framework import serializers

from accounts.models import FarmerProfile
from marketlink_core.geo import rounded
from markets.serializers import ClosureSerializer


class FarmerSummarySerializer(serializers.ModelSerializer):
    # farmer_profiles is keyed by user_id, so the profile pk is the user id.
    id = serializers.IntegerField(source="user_id", read_only=True)
    rating_avg = serializers.SerializerMethodField()
    rating_count = serializers.IntegerField(read_only=True, default=0)
    in_stock_product_count = serializers.IntegerField(read_only=True, default=0)
    markets = serializers.SerializerMethodField()
    upcoming_closures = serializers.SerializerMethodField()
    distance_km = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()

    class Meta:
        model = FarmerProfile
        fields = [
            "id",
            "stall_name",
            "image",
            "rating_avg",
            "rating_count",
            "markets",
            "operating_days",
            "in_stock_product_count",
            "upcoming_closures",
            "distance_km",
            "is_favorite",
        ]
        read_only_fields = fields

    def get_rating_avg(self, farmer) -> float | None:
        value = getattr(farmer, "rating_avg", None)
        return round(value, 2) if value is not None else None

    def get_markets(self, farmer) -> list[dict]:
        rows = self.context.get("markets", {}).get(farmer.pk, [])
        only = self.context.get("only_market_id")
        return [row for row in rows if only is None or row["market_id"] == only]

    def get_upcoming_closures(self, farmer) -> list[dict]:
        rows = self.context.get("closures", {}).get(farmer.pk, [])
        return ClosureSerializer(rows, many=True).data

    def get_distance_km(self, farmer) -> float | None:
        return rounded(getattr(farmer, "distance", None))

    def get_is_favorite(self, farmer) -> bool | None:
        favorites = self.context.get("favorite_farmer_ids")
        return None if favorites is None else farmer.pk in favorites


class FarmerPublicSerializer(FarmerSummarySerializer):
    """The public stall page. Shoppers meet the stall at its market, so the farmer's own
    address and map pin (often their home) are left out; the admin serializer adds them."""

    pickup_windows = serializers.SerializerMethodField()

    class Meta(FarmerSummarySerializer.Meta):
        fields = [
            *FarmerSummarySerializer.Meta.fields,
            "contact_person",
            "phone",
            "description",
            "order_cutoff_hours",
            "pickup_windows",
        ]
        read_only_fields = fields

    def get_pickup_windows(self, farmer) -> list[dict]:
        return self.context.get("pickup_windows", [])
