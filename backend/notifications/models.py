from django.conf import settings
from django.db import models
from django.db.models import F, Q

from marketlink_core.models import BaseModel, CreatedAtModel


class NotificationType(models.TextChoices):
    # Customer notifications
    ORDER_ACCEPTED = "ORDER_ACCEPTED", "Order Accepted"
    ORDER_READY = "ORDER_READY", "Order Ready for Pickup"
    ORDER_DECLINED = "ORDER_DECLINED", "Order Declined"
    ORDER_EXPIRED = "ORDER_EXPIRED", "Order Expired"
    ORDER_CHANGE_APPROVED = "ORDER_CHANGE_APPROVED", "Order Change Request Approved"
    ORDER_CHANGE_REJECTED = "ORDER_CHANGE_REJECTED", "Order Change Request Rejected"
    ORDER_ITEM_SOLD_OUT = "ORDER_ITEM_SOLD_OUT", "Order Item Sold Out"
    RESTOCK = "RESTOCK", "Favorite Product Restocked"
    # Farmer notifications
    ORDER_PLACED = "ORDER_PLACED", "New Order Placed"
    ORDER_MODIFIED = "ORDER_MODIFIED", "Order Modified by Customer"
    ORDER_CANCELLED = "ORDER_CANCELLED", "Order Cancelled by Customer"
    ORDER_CANCELLED_CUSTOMER_LOCKED = (
        "ORDER_CANCELLED_CUSTOMER_LOCKED",
        "Order Cancelled Due to Customer Lock",
    )
    ACCOUNT_STATUS_CHANGED = "ACCOUNT_STATUS_CHANGED", "Account Status Changed"
    MARKET_SCHEDULE_CHANGED = "MARKET_SCHEDULE_CHANGED", "Market Schedule Changed"
    # Sent to both sides when Admin closes a market (AD-17), carrying the reason they gave.
    MARKET_CLOSED = "MARKET_CLOSED", "Market Closed"



class AnnouncementAudience(models.TextChoices):
    ALL = "ALL", "All"
    CUSTOMER = "CUSTOMER", "Customer"
    FARMER = "FARMER", "Farmer"


class Notification(CreatedAtModel):
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="notifications"
    )
    type = models.CharField(max_length=40, choices=NotificationType.choices)
    title = models.CharField(max_length=150)
    message = models.CharField(max_length=500)
    target_url = models.CharField(max_length=255, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(
                fields=["recipient", "is_read", "created_at"], name="notif_recipient_read_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"{self.type} -> {self.recipient_id}"


class Announcement(BaseModel):
    title = models.CharField(max_length=150)
    content = models.CharField(max_length=1000)
    audience = models.CharField(
        max_length=20, choices=AnnouncementAudience.choices, default=AnnouncementAudience.ALL
    )
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="announcements",
    )

    class Meta:
        db_table = "announcements"
        ordering = ["-starts_at"]
        indexes = [
            models.Index(
                fields=["is_active", "audience", "starts_at"], name="ann_active_aud_start_idx"
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(ends_at__isnull=True) | Q(ends_at__gt=F("starts_at")),
                name="ann_ends_after_starts",
            ),
        ]

    def __str__(self) -> str:
        return self.title
