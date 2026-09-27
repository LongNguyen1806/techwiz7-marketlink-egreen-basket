from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from accounts.admin_portal.serializers_admin import OpenOrderBreakdownSerializer
from accounts.models import FarmerStatus
from catalog.models import Category, Product

NAME_MIN_LENGTH = 2
NAME_MAX_LENGTH = 50
DUPLICATE_NAME_MESSAGE = "A category with this name already exists."
REASON_MIN_LENGTH = 5
REASON_MAX_LENGTH = 500


class Availability:
    IN_STOCK = "IN_STOCK"
    OUT_OF_STOCK = "OUT_OF_STOCK"
    UNAVAILABLE = "UNAVAILABLE"


class CategoryAdminReadSerializer(serializers.ModelSerializer):
    # Annotated by catalog.selectors.list_categories_for_admin; the default keeps the
    # serializer usable for a freshly created row that was never annotated.
    product_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Category
        fields = ["id", "name", "icon", "display_order", "is_active", "product_count"]
        read_only_fields = fields


class CategoryAdminWriteSerializer(serializers.ModelSerializer):
    # Declaring `name` here replaces the auto-built field, which would have carried
    # the model's UniqueValidator, so the validator is restored explicitly. The
    # lookup runs under the column's utf8mb4_0900_as_ci collation: accent-sensitive,
    # case-insensitive, exactly as A-07 requires.
    name = serializers.CharField(
        min_length=NAME_MIN_LENGTH,
        max_length=NAME_MAX_LENGTH,
        validators=[
            UniqueValidator(queryset=Category.objects.all(), message=DUPLICATE_NAME_MESSAGE)
        ],
    )

    class Meta:
        model = Category
        fields = ["name", "icon", "display_order", "is_active"]

    def validate_name(self, value: str) -> str:
        return value.strip()


class ModerationReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=REASON_MIN_LENGTH, max_length=REASON_MAX_LENGTH)


class ProductAdminSerializer(serializers.ModelSerializer):
    price = serializers.DecimalField(max_digits=10, decimal_places=2, coerce_to_string=True)
    category = serializers.SerializerMethodField()
    farmer = serializers.SerializerMethodField()
    markets = serializers.SerializerMethodField()
    availability = serializers.SerializerMethodField()
    held_quantity = serializers.SerializerMethodField()
    pending_quantity = serializers.SerializerMethodField()
    rating_avg = serializers.FloatField(read_only=True)
    rating_count = serializers.IntegerField(read_only=True, default=0)
    is_favorite = serializers.SerializerMethodField()
    hidden_by_email = serializers.EmailField(source="hidden_by.email", read_only=True, default=None)
    open_order_count = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = [
            "id",
            "name",
            "description",
            "image",
            "price",
            "unit",
            "stock_quantity",
            "weekly_default_quantity",
            "held_quantity",
            "pending_quantity",
            "is_available",
            "availability",
            "is_archived",
            "is_hidden_by_admin",
            "moderation_action",
            "hidden_reason",
            "hidden_at",
            "hidden_by_email",
            "open_order_count",
            "category",
            "farmer",
            "markets",
            "rating_avg",
            "rating_count",
            "is_favorite",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_open_order_count(self, product) -> int:
        return self.context.get("open_order_counts", {}).get(product.pk, 0)

    @property
    def _context_maps(self) -> tuple[dict, dict]:
        return self.context.get("held_quantities", {}), self.context.get("markets", {})

    def get_category(self, product) -> dict:
        return {"id": product.category_id, "name": product.category.name}

    def get_farmer(self, product) -> dict:
        return {"id": product.farmer_id, "stall_name": product.farmer.stall_name}

    def get_markets(self, product) -> list[dict]:
        return self._context_maps[1].get(product.pk, [])

    def get_held_quantity(self, product) -> int:
        return self._context_maps[0].get(product.pk, 0)

    def get_pending_quantity(self, product) -> int:
        return self.context.get("pending_quantities", {}).get(product.pk, 0)

    def get_availability(self, product) -> str:
        # "Publicly on sale" is defined in §3.3: not archived, not hidden, farmer APPROVED.
        sellable = (
            not product.is_archived
            and not product.is_hidden_by_admin
            and product.farmer.status == FarmerStatus.APPROVED
        )
        if not sellable or not product.is_available:
            return Availability.UNAVAILABLE
        return Availability.IN_STOCK if product.stock_quantity else Availability.OUT_OF_STOCK

    # Part of ProductCard, which ProductDetail and FarmerProduct extend; an admin has no
    # favourites, so it stays null here.
    @extend_schema_field(serializers.BooleanField(allow_null=True))
    def get_is_favorite(self, product):
        return None


class ProductBlockImpactSerializer(serializers.Serializer):
    """What a takedown would cost.

    The breakdown component is the one AD-04 already publishes, not a copy of it: two
    identically named components with different identities make drf-spectacular emit a
    warning and then pick one of them at random for both.
    """

    open_orders = OpenOrderBreakdownSerializer()
    affected_customers = serializers.IntegerField()
