from decimal import Decimal
from typing import Any

from rest_framework import serializers

from catalog.models import Category, Product, Unit
from catalog.services.farmer_product import build_product_metrics, validate_image_upload


class FarmerProductCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name"]


class FarmerProductSerializer(serializers.ModelSerializer):
    """FarmerProduct (Pass 4B §3.3). Batch data comes from context["product_metrics"]."""

    category = FarmerProductCategorySerializer(read_only=True)
    availability = serializers.SerializerMethodField()
    farmer = serializers.SerializerMethodField()
    rating_avg = serializers.SerializerMethodField()
    rating_count = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()
    markets = serializers.SerializerMethodField()
    held_quantity = serializers.SerializerMethodField()
    pending_quantity = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "image",
            "price",
            "unit",
            "stock_quantity",
            "is_available",
            "availability",
            "category",
            "farmer",
            "rating_avg",
            "rating_count",
            "is_favorite",
            "description",
            "markets",
            "weekly_default_quantity",
            "held_quantity",
            "pending_quantity",
            "is_archived",
            "is_hidden_by_admin",
            "hidden_reason",
            "created_at",
            "updated_at",
        ]

    def _metrics(self, obj: Product) -> dict[str, Any]:
        metrics = self.context.get("product_metrics")
        if metrics is None:
            metrics = build_product_metrics(farmer=obj.farmer, product_ids=[obj.id])
            self.context["product_metrics"] = metrics
        return metrics

    def get_availability(self, obj: Product) -> str:
        if not obj.is_available:
            return "UNAVAILABLE"
        return "IN_STOCK" if obj.stock_quantity > 0 else "OUT_OF_STOCK"

    def get_farmer(self, obj: Product) -> dict[str, Any]:
        return {"id": obj.farmer_id, "stall_name": obj.farmer.stall_name}

    def get_rating_avg(self, obj: Product) -> float | None:
        rating = self._metrics(obj)["ratings"].get(obj.id)
        return rating[0] if rating else None

    def get_rating_count(self, obj: Product) -> int:
        rating = self._metrics(obj)["ratings"].get(obj.id)
        return rating[1] if rating else 0

    def get_is_favorite(self, obj: Product) -> None:
        return None  # only meaningful for customers

    def get_markets(self, obj: Product) -> list[dict[str, Any]]:
        return self._metrics(obj)["markets"]

    def get_held_quantity(self, obj: Product) -> int:
        return self._metrics(obj)["held"].get(obj.id, 0)

    def get_pending_quantity(self, obj: Product) -> int:
        return self._metrics(obj)["pending"].get(obj.id, 0)


class FarmerProductCreateSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=2, max_length=100, required=True)
    category_id = serializers.IntegerField(required=True)
    price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        max_value=Decimal("10000.00"),
        required=True,
    )
    unit = serializers.ChoiceField(choices=Unit.choices, required=True)
    stock_quantity = serializers.IntegerField(min_value=0, required=True)
    weekly_default_quantity = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    description = serializers.CharField(max_length=1000, required=False, allow_blank=True, allow_null=True)
    image = serializers.FileField(required=False, allow_null=True)
    is_available = serializers.BooleanField(required=False, default=True)

    def validate_category_id(self, value: int) -> int:
        if not Category.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Category does not exist or is inactive.")
        return value

    def validate_image(self, value: Any) -> Any:
        # The re-encoded copy is stored, never the uploaded bytes.
        return validate_image_upload(value) if value else value


class FarmerProductUpdateSerializer(serializers.Serializer):
    name = serializers.CharField(min_length=2, max_length=100, required=False)
    category_id = serializers.IntegerField(required=False)
    price = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        min_value=Decimal("0.01"),
        max_value=Decimal("10000.00"),
        required=False,
    )
    unit = serializers.ChoiceField(choices=Unit.choices, required=False)
    stock_quantity = serializers.IntegerField(min_value=0, required=False)
    weekly_default_quantity = serializers.IntegerField(min_value=0, required=False, allow_null=True)
    description = serializers.CharField(max_length=1000, required=False, allow_blank=True, allow_null=True)
    image = serializers.FileField(required=False, allow_null=True)
    is_available = serializers.BooleanField(required=False)

    def validate_category_id(self, value: int) -> int:
        if not Category.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Category does not exist or is inactive.")
        return value

    def validate_image(self, value: Any) -> Any:
        # The re-encoded copy is stored, never the uploaded bytes.
        return validate_image_upload(value) if value else value


class WeeklyTemplateRowSerializer(serializers.Serializer):
    product_id = serializers.IntegerField()
    name = serializers.CharField()
    weekly_default_quantity = serializers.IntegerField(allow_null=True)
    held_quantity = serializers.IntegerField()
    pending_quantity = serializers.IntegerField()
    current_stock = serializers.IntegerField()
    new_stock = serializers.IntegerField()
    is_available = serializers.BooleanField()
