from rest_framework import serializers

from catalog.admin_portal.serializers_admin import Availability
from catalog.models import Category, Product


class CategoryPublicSerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ["id", "name", "icon", "display_order"]
        read_only_fields = fields


class ProductCardSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=True)
    category = serializers.SerializerMethodField()
    farmer = serializers.SerializerMethodField()
    availability = serializers.SerializerMethodField()
    rating_avg = serializers.SerializerMethodField()
    rating_count = serializers.IntegerField(read_only=True, default=0)
    is_favorite = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "image",
            "price",
            "unit",
            "stock_quantity",
            "min_per_order",
            "max_per_order",
            "is_available",
            "availability",
            "category",
            "farmer",
            "rating_avg",
            "rating_count",
            "is_favorite",
        ]
        read_only_fields = fields

    def get_category(self, product) -> dict:
        return {"id": product.category_id, "name": product.category.name}

    def get_farmer(self, product) -> dict:
        return {"id": product.farmer_id, "stall_name": product.farmer.stall_name}

    def get_availability(self, product) -> str:
        # Rows reaching a public endpoint already pass the §6.2 visibility filter, so only
        # the seller's own switches are left to check.
        if not product.is_available:
            return Availability.UNAVAILABLE
        return Availability.IN_STOCK if product.stock_quantity else Availability.OUT_OF_STOCK

    def get_rating_avg(self, product) -> float | None:
        value = getattr(product, "rating_avg", None)
        return round(value, 2) if value is not None else None

    def get_is_favorite(self, product) -> bool | None:
        favorites = self.context.get("favorite_product_ids")
        return None if favorites is None else product.pk in favorites


class ProductDetailSerializer(ProductCardSerializer):
    markets = serializers.SerializerMethodField()

    class Meta(ProductCardSerializer.Meta):
        fields = [*ProductCardSerializer.Meta.fields, "description", "markets"]
        read_only_fields = fields

    def get_markets(self, product) -> list[dict]:
        return self.context.get("markets", {}).get(product.pk, [])
