from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import F, Q
from simple_history.models import HistoricalRecords

from marketlink_core.models import BaseModel, CreatedAtModel, HistoryRequestMeta, UUIDUploadTo


class Unit(models.TextChoices):
    """How farm produce is sold at a Vietnamese market."""

    KG = "KG", "Kilogram"
    BUNCH = "BUNCH", "Bunch"
    EACH = "EACH", "Each"
    BAG = "BAG", "Bag"
    BOX = "BOX", "Box"
    PACK = "PACK", "Pack"


class ModerationAction(models.TextChoices):
    """Why a product is hidden, which decides what else the action did.

    HIDE is an investigation: the listing goes dark, every order placed against it stands.
    BLOCK is a takedown: the listing goes dark *and* every open order containing it is
    declined and restocked. Both write the same `is_hidden_by_admin` flag, so no public
    query has to learn about this column; it only records which of the two happened, and
    therefore whether Restore or Unblock is the way back.
    """

    HIDE = "HIDE", "Hidden for investigation"
    BLOCK = "BLOCK", "Blocked for legal violation"


class ReviewStatus(models.TextChoices):
    """Whether a listing has been through an admin.

    A stall writes the listing; an admin decides whether shoppers see it. Before this, a
    listing went live the moment it was saved and the only lever afterwards was to hide it,
    which is a decision taken too late and in front of an audience.
    """

    PENDING = "PENDING", "Waiting for review"
    APPROVED = "APPROVED", "Approved"
    REJECTED = "REJECTED", "Rejected"


REVIEWABLE_FIELDS = ("name", "description", "image", "category_id")

MAX_ORDER_QUANTITY = 999

ON_SALE_FILTER = Q(
    is_available=True, is_archived=False, is_hidden_by_admin=False, review_status=ReviewStatus.APPROVED
)


class Category(BaseModel):
    name = models.CharField(max_length=50, unique=True, db_collation="utf8mb4_0900_as_ci")
    icon = models.CharField(max_length=50, unique=True)
    display_order = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        db_table = "categories"
        ordering = ["display_order", "name"]

    def __str__(self) -> str:
        return self.name


class Product(BaseModel):
    farmer = models.ForeignKey(
        "accounts.FarmerProfile", on_delete=models.RESTRICT, related_name="products"
    )
    category = models.ForeignKey(Category, on_delete=models.RESTRICT, related_name="products")
    name = models.CharField(max_length=100)
    description = models.TextField(null=True, blank=True)
    image = models.ImageField(
        upload_to=UUIDUploadTo("products"), max_length=255, null=True, blank=True
    )
    price = models.DecimalField(max_digits=10, decimal_places=2)
    unit = models.CharField(max_length=10, choices=Unit.choices)

    stock_quantity = models.PositiveIntegerField(default=0)
    weekly_default_quantity = models.PositiveIntegerField(null=True, blank=True)
    min_per_order = models.PositiveSmallIntegerField(default=1)
    max_per_order = models.PositiveSmallIntegerField(null=True, blank=True)

    is_available = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)

    review_status = models.CharField(
        max_length=10, choices=ReviewStatus.choices, default=ReviewStatus.PENDING
    )
    review_note = models.CharField(max_length=500, null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_products",
    )

    is_hidden_by_admin = models.BooleanField(default=False)
    moderation_action = models.CharField(
        max_length=10, choices=ModerationAction.choices, null=True, blank=True
    )
    hidden_reason = models.CharField(max_length=500, null=True, blank=True)
    hidden_at = models.DateTimeField(null=True, blank=True)
    hidden_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="hidden_products",
    )

    history = HistoricalRecords(
        table_name="product_histories",
        bases=[HistoryRequestMeta],
    )

    class Meta:
        db_table = "products"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["farmer", "is_archived"], name="prod_farmer_arch_idx"),
            models.Index(
                fields=["category", "is_archived", "is_hidden_by_admin"],
                name="prod_cat_arch_hidden_idx",
            ),
            models.Index(fields=["price"], name="prod_price_idx"),
            models.Index(fields=["created_at"], name="prod_created_idx"),
            models.Index(fields=["review_status", "created_at"], name="prod_review_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(price__gte=Decimal("0.01"), price__lte=Decimal("10000.00")),
                name="prod_price_range",
            ),
            models.CheckConstraint(
                condition=Q(max_per_order__isnull=True)
                | Q(max_per_order__gte=1, max_per_order__lte=MAX_ORDER_QUANTITY),
                name="prod_max_per_order_range",
            ),
            models.CheckConstraint(
                condition=Q(min_per_order__gte=1, min_per_order__lte=MAX_ORDER_QUANTITY)
                & (Q(max_per_order__isnull=True) | Q(min_per_order__lte=F("max_per_order"))),
                name="prod_min_per_order_range",
            ),
        ]

    def __str__(self) -> str:
        return self.name

    @property
    def is_on_sale(self) -> bool:
        """Row-level twin of ON_SALE_FILTER, for code that already holds the product."""
        return (
            self.is_available
            and not self.is_archived
            and not self.is_hidden_by_admin
            and self.review_status == ReviewStatus.APPROVED
        )


class ProductMarket(CreatedAtModel):
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="market_links")
    farmer_market = models.ForeignKey(
        "markets.FarmerMarket", on_delete=models.CASCADE, related_name="product_links"
    )

    class Meta:
        db_table = "product_markets"
        constraints = [
            models.UniqueConstraint(fields=["product", "farmer_market"], name="pm_uniq_product_stall"),
        ]

    def __str__(self) -> str:
        return f"{self.product_id} at {self.farmer_market_id}"




class AIVerdict(models.TextChoices):
    PASS = "PASS", "Nothing found"
    NEEDS_REVIEW = "NEEDS_REVIEW", "Worth a closer look"
    LIKELY_VIOLATION = "LIKELY_VIOLATION", "Likely breaks the rules"
    UNAVAILABLE = "UNAVAILABLE", "AI check unavailable"


class AIReviewKind(models.TextChoices):
    LISTING = "LISTING", "New or edited listing"
    WEEKLY_IMAGE = "WEEKLY_IMAGE", "Weekly photo check"


class AIAutoAction(models.TextChoices):
    APPROVED = "APPROVED", "Approved by AI"
    HELD = "HELD", "Held by AI"


class ProductAIReview(CreatedAtModel):
    """One advisory pass over a listing. Rows are never updated except to record what the
    admin then decided, so the history shows how the advice and the decisions compare."""

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="ai_reviews")
    kind = models.CharField(max_length=15, choices=AIReviewKind.choices)
    content_hash = models.CharField(max_length=64)
    verdict = models.CharField(max_length=20, choices=AIVerdict.choices)
    risk_score = models.PositiveSmallIntegerField(default=0)
    findings = models.JSONField(default=list)
    summary = models.CharField(max_length=500, blank=True, default="")
    suggested_category = models.ForeignKey(
        Category, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    ai_used = models.BooleanField(default=False)
    ai_error = models.CharField(max_length=300, null=True, blank=True)
    model_name = models.CharField(max_length=60, blank=True, default="")
    prompt_version = models.CharField(max_length=20, blank=True, default="")
    rules_version = models.CharField(max_length=20, blank=True, default="")
    duration_ms = models.PositiveIntegerField(null=True, blank=True)
    admin_decision = models.CharField(max_length=10, choices=ReviewStatus.choices, null=True, blank=True)
    admin_decided_at = models.DateTimeField(null=True, blank=True)
    auto_action = models.CharField(max_length=10, choices=AIAutoAction.choices, null=True, blank=True)
    auto_action_at = models.DateTimeField(null=True, blank=True)
    admin_checked_at = models.DateTimeField(null=True, blank=True)
    admin_checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        db_table = "product_ai_reviews"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["product", "kind", "-created_at"], name="ai_review_latest_idx"),
            models.Index(fields=["verdict", "created_at"], name="ai_review_verdict_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.product_id} {self.kind} {self.verdict}"


class PriceGuideline(BaseModel):
    """What a sensible listing looks like for one category and unit. Outside it is not
    forbidden, only worth an admin's look; admins tune the numbers."""

    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name="price_guidelines")
    unit = models.CharField(max_length=10, choices=Unit.choices)
    min_price = models.DecimalField(max_digits=10, decimal_places=2)
    max_price = models.DecimalField(max_digits=10, decimal_places=2)
    max_stock = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        db_table = "price_guidelines"
        ordering = ["category__display_order", "category__name", "unit"]
        constraints = [
            models.UniqueConstraint(fields=["category", "unit"], name="price_guideline_uniq"),
            models.CheckConstraint(
                condition=Q(min_price__gte=Decimal("0.01"), max_price__lte=Decimal("10000.00"))
                & Q(min_price__lte=F("max_price")),
                name="price_guideline_range",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.category} {self.unit} {self.min_price}-{self.max_price}"
