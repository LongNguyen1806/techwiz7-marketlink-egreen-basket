from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Q
from simple_history.models import HistoricalRecords

from marketlink_core.models import BaseModel, HistoryRequestMeta, UUIDUploadTo


class Unit(models.TextChoices):
    KG = "KG", "Kilogram"
    BUNCH = "BUNCH", "Bunch"
    PIECE = "PIECE", "Piece"
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


# Changing any of these is changing what the listing *claims to be*, so it goes back into the
# queue. Price and stock are deliberately absent: a stall that has to wait for an admin before
# it can correct its own stock level will stop correcting it, and then the stock figure - the
# one number the whole booking flow rests on - becomes fiction.
REVIEWABLE_FIELDS = ("name", "description", "image", "category_id")


class Category(BaseModel):
    name = models.CharField(max_length=50, unique=True, db_collation="utf8mb4_0900_as_ci")
    # Unique, and required: a picture shared by two categories is a symbol that means two
    # things, which reads worse on the shopper's home page than no picture at all. The set of
    # permitted names lives in catalog/icons.py and the serializer refuses anything else.
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

    is_available = models.BooleanField(default=True)
    is_archived = models.BooleanField(default=False)

    # The approval state is separate from the hidden flag on purpose: "nobody has looked at
    # this yet" and "an admin looked and took it down" are different facts, and a listing can
    # be waiting for a second review while an earlier approved version is still on sale.
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
    # NULL whenever is_hidden_by_admin is False; the two are cleared together.
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
            # The approval queue is read far more often than it is written to, and it is
            # always read as "everything still waiting, oldest first".
            models.Index(fields=["review_status", "created_at"], name="prod_review_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(price__gte=Decimal("0.01"), price__lte=Decimal("10000.00")),
                name="prod_price_range",
            ),
        ]

    def __str__(self) -> str:
        return self.name
