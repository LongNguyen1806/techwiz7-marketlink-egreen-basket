from django.conf import settings
from django.db import models
from django.db.models import F, Q
from simple_history.models import HistoricalRecords

from catalog.models import Unit
from marketlink_core.models import BaseModel, CreatedAtModel, HistoryRequestMeta


class OrderStatus(models.TextChoices):
    PLACED = "PLACED", "Placed"
    ACCEPTED = "ACCEPTED", "Accepted"
    READY_FOR_PICKUP = "READY_FOR_PICKUP", "Ready for Pickup"
    COMPLETED = "COMPLETED", "Completed"
    CANCELLED = "CANCELLED", "Cancelled"
    DECLINED = "DECLINED", "Declined"
    NO_SHOW = "NO_SHOW", "No Show"
    EXPIRED = "EXPIRED", "Expired"


OPEN_STATUSES = (
    OrderStatus.PLACED,
    OrderStatus.ACCEPTED,
    OrderStatus.READY_FOR_PICKUP,
)


class ActorRole(models.TextChoices):
    CUSTOMER = "CUSTOMER", "Customer"
    FARMER = "FARMER", "Farmer"
    ADMIN = "ADMIN", "Administrator"
    SYSTEM = "SYSTEM", "System"


class Transition(models.TextChoices):
    T1 = "T1", "Create Order"
    T2 = "T2", "Approve Placed Order"
    T3 = "T3", "Decline Placed Order"
    T4 = "T4", "Decline Accepted Order"
    T5 = "T5", "Customer Cancel Placed Order"
    T6 = "T6", "Customer Cancel Accepted Order"
    T7 = "T7", "Deprecated - Customer Modify Accepted Order"
    T8 = "T8", "System Expire Order"
    T9 = "T9", "Ready For Pickup"
    T10 = "T10", "Complete Order"
    T11 = "T11", "Mark No Show"
    T12 = "T12", "Admin Suspend Farmer"
    T13 = "T13", "Admin Lock Customer"
    T14 = "T14", "Mark No Show For Accepted Order"


class ChangeReason:
    SYSTEM_EXPIRED = "SYSTEM_EXPIRED"
    FARMER_SUSPENDED_BY_ADMIN = "FARMER_SUSPENDED_BY_ADMIN"
    CUSTOMER_LOCKED_BY_ADMIN = "CUSTOMER_LOCKED_BY_ADMIN"
    MARKET_CLOSED_BY_ADMIN = "MARKET_CLOSED_BY_ADMIN"


MONEY_FIELD_KWARGS = {"max_digits": 10, "decimal_places": 2}


class Order(BaseModel):
    customer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.RESTRICT, related_name="orders"
    )
    farmer = models.ForeignKey(
        "accounts.FarmerProfile", on_delete=models.RESTRICT, related_name="orders"
    )
    market = models.ForeignKey("markets.Market", on_delete=models.RESTRICT, related_name="orders")
    pickup_slot = models.ForeignKey(
        "markets.PickupSlot",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="orders",
    )
    stall_label = models.CharField(max_length=100, null=True, blank=True)

    pickup_date = models.DateField()
    pickup_start_at = models.DateTimeField()
    pickup_end_at = models.DateTimeField()
    cutoff_at = models.DateTimeField()

    status = models.CharField(
        max_length=20, choices=OrderStatus.choices, default=OrderStatus.PLACED
    )
    note = models.CharField(max_length=300, null=True, blank=True)
    pending_change = models.JSONField(null=True, blank=True)
    total_amount = models.DecimalField(**MONEY_FIELD_KWARGS)
    version = models.PositiveIntegerField(default=1)

    history = HistoricalRecords(
        table_name="order_histories",
        bases=[HistoryRequestMeta],
    )

    class Meta:
        db_table = "orders"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["farmer", "status", "pickup_start_at"], name="ord_farmer_status_pick_idx"
            ),
            models.Index(fields=["customer", "status"], name="ord_customer_status_idx"),
            models.Index(
                fields=["customer", "farmer", "status"], name="ord_cust_farmer_status_idx"
            ),
            models.Index(fields=["status", "pickup_start_at"], name="ord_status_pick_idx"),
            models.Index(
                fields=["market", "status", "pickup_date"], name="ord_market_status_date_idx"
            ),
            models.Index(fields=["created_at"], name="ord_created_idx"),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(pickup_end_at__gt=F("pickup_start_at")),
                name="ord_pickup_end_after_start",
            ),
            models.CheckConstraint(
                condition=Q(cutoff_at__lte=F("pickup_start_at")),
                name="ord_cutoff_before_pickup",
            ),
            models.CheckConstraint(condition=Q(total_amount__gte=0), name="ord_total_non_negative"),
        ]

    def __str__(self) -> str:
        return f"#{self.pk}"

    @property
    def is_open(self) -> bool:
        return self.status in OPEN_STATUSES


class OrderItem(BaseModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(
        "catalog.Product", on_delete=models.RESTRICT, related_name="order_items"
    )
    product_name = models.CharField(max_length=100)
    unit = models.CharField(max_length=10, choices=Unit.choices)
    unit_price = models.DecimalField(**MONEY_FIELD_KWARGS)
    quantity = models.PositiveIntegerField()
    line_total = models.DecimalField(**MONEY_FIELD_KWARGS)

    history = HistoricalRecords(
        table_name="order_item_histories",
        bases=[HistoryRequestMeta],
    )

    class Meta:
        db_table = "order_items"
        ordering = ["id"]
        indexes = [
            models.Index(fields=["product"], name="oitem_product_idx"),
        ]
        constraints = [
            models.UniqueConstraint(fields=["order", "product"], name="oitem_uniq_order_product"),
            models.CheckConstraint(condition=Q(quantity__gte=1), name="oitem_quantity_min_1"),
            models.CheckConstraint(condition=Q(unit_price__gte=0), name="oitem_price_non_negative"),
        ]

    def __str__(self) -> str:
        return f"{self.product_name} x{self.quantity}"


class OrderStatusHistory(CreatedAtModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_history")
    from_status = models.CharField(
        max_length=20, choices=OrderStatus.choices, null=True, blank=True
    )
    to_status = models.CharField(max_length=20, choices=OrderStatus.choices)
    transition = models.CharField(
        max_length=10, choices=Transition.choices, null=True, blank=True
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="order_status_actions",
    )
    actor_role = models.CharField(max_length=20, choices=ActorRole.choices)
    change_reason = models.TextField(null=True, blank=True)
    request_id = models.CharField(max_length=36, null=True, blank=True)

    class Meta:
        db_table = "order_status_history"
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=["order", "created_at"], name="osh_order_created_idx"),
        ]

    def __str__(self) -> str:
        return f"#{self.order_id}: {self.from_status} -> {self.to_status}"
