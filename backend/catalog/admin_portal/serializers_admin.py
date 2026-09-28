from decimal import Decimal

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from accounts.admin_portal.serializers_admin import OpenOrderBreakdownSerializer
from accounts.models import FarmerStatus
from catalog.icons import canonical_icon
from catalog.models import Category, PriceGuideline, Product, ProductAIReview

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


DUPLICATE_ICON_MESSAGE = "Another category already uses this icon."
UNKNOWN_ICON_MESSAGE = "Choose one of the icons offered."


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

    # A free-text icon name used to be accepted and then drawn as a leaf if nothing matched,
    # so a typo became a wrong picture on the shopper's home page with nothing to notice.
    # Kept as a CharField rather than a ChoiceField because an older name has to be readable
    # and rewritten, and a ChoiceField refuses it before any of that can run.
    icon = serializers.CharField(max_length=50)

    class Meta:
        model = Category
        fields = ["name", "icon", "display_order", "is_active"]

    def validate_name(self, value: str) -> str:
        return value.strip()

    def validate_icon(self, value: str) -> str:
        # Accepts the names an older database stored, so editing a category seeded before the
        # icon set was widened does not fail on a value the admin never typed.
        icon = canonical_icon(value)
        if icon is None:
            raise serializers.ValidationError(UNKNOWN_ICON_MESSAGE)
        # Checked here rather than with a UniqueValidator on the field: that one would test
        # the name as typed, and "pepper" is free while the "chilli" it becomes may not be.
        clash = Category.objects.filter(icon=icon)
        if self.instance is not None:
            clash = clash.exclude(pk=self.instance.pk)
        if clash.exists():
            raise serializers.ValidationError(DUPLICATE_ICON_MESSAGE)
        return icon


class ModerationReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=REASON_MIN_LENGTH, max_length=REASON_MAX_LENGTH)


class AIReviewSerializer(serializers.ModelSerializer):
    """The AI's advice on a listing, as the approval queue shows it. Advice, not a decision."""

    suggested_category = serializers.SerializerMethodField()

    class Meta:
        model = ProductAIReview
        fields = [
            "id",
            "kind",
            "verdict",
            "risk_score",
            "summary",
            "findings",
            "suggested_category",
            "ai_used",
            "ai_error",
            "model_name",
            "admin_decision",
            "created_at",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_suggested_category(self, review):
        category = review.suggested_category
        return {"id": category.pk, "name": category.name} if category else None


class PriceGuidelineSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True)
    min_price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"), max_value=Decimal("10000.00"))
    max_price = serializers.DecimalField(max_digits=10, decimal_places=2, min_value=Decimal("0.01"), max_value=Decimal("10000.00"))
    max_stock = serializers.IntegerField(min_value=1, required=False, allow_null=True)

    class Meta:
        model = PriceGuideline
        fields = ["id", "category", "category_name", "unit", "min_price", "max_price", "max_stock", "updated_at"]
        read_only_fields = ["id", "category_name", "updated_at"]
        validators = [
            serializers.UniqueTogetherValidator(
                queryset=PriceGuideline.objects.all(),
                fields=["category", "unit"],
                message="This category and unit already have a guideline.",
            )
        ]

    def validate(self, attrs):
        low = attrs.get("min_price", getattr(self.instance, "min_price", None))
        high = attrs.get("max_price", getattr(self.instance, "max_price", None))
        if low is not None and high is not None and low > high:
            raise serializers.ValidationError({"min_price": ["The lowest price cannot be above the highest."]})
        return attrs


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
    ai_review = serializers.SerializerMethodField()
    ai_photo_check = serializers.SerializerMethodField()

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
            "review_status",
            "review_note",
            "reviewed_at",
            "is_hidden_by_admin",
            "moderation_action",
            "hidden_reason",
            "hidden_at",
            "hidden_by_email",
            "open_order_count",
            "ai_review",
            "ai_photo_check",
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

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_ai_review(self, product):
        review = self.context.get("ai_reviews", {}).get(product.pk)
        return AIReviewSerializer(review).data if review else None

    @extend_schema_field(serializers.DictField(allow_null=True))
    def get_ai_photo_check(self, product):
        review = self.context.get("ai_photo_checks", {}).get(product.pk)
        return AIReviewSerializer(review).data if review else None

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


class AIDecisionSerializer(serializers.ModelSerializer):
    """#8: one thing the AI decided on its own, and whether an admin has looked at it since."""

    product = serializers.SerializerMethodField()
    checked_by = serializers.EmailField(source="admin_checked_by.email", default=None, read_only=True)

    class Meta:
        model = ProductAIReview
        fields = [
            "id",
            "product",
            "verdict",
            "risk_score",
            "summary",
            "findings",
            "auto_action",
            "auto_action_at",
            "admin_decision",
            "admin_checked_at",
            "checked_by",
        ]
        read_only_fields = fields

    @extend_schema_field(serializers.DictField())
    def get_product(self, review) -> dict:
        product = review.product
        return {
            "id": product.pk,
            "name": product.name,
            "stall_name": product.farmer.stall_name,
            "farmer_id": product.farmer_id,
            "category": product.category.name if product.category_id else None,
            "review_status": product.review_status,
            "image": product.image.url if product.image else None,
        }
