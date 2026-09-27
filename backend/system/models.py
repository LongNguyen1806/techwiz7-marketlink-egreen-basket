from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from marketlink_core.models import BaseModel, CreatedAtModel


class AuditAction(models.TextChoices):
    LOGIN = "LOGIN", "Login"
    LOGIN_FAILED = "LOGIN_FAILED", "Login Failed"
    ACCOUNT_REGISTERED = "ACCOUNT_REGISTERED", "Account Registered"
    LOGOUT = "LOGOUT", "Logout"
    PASSWORD_CHANGED = "PASSWORD_CHANGED", "Change Password"
    ACCESS_DENIED = "ACCESS_DENIED", "Access Denied"
    EXPORT_DATA = "EXPORT_DATA", "Export Data"
    FARMER_APPROVED = "FARMER_APPROVED", "Approve Farmer"
    FARMER_REJECTED = "FARMER_REJECTED", "Reject Farmer"
    FARMER_SUSPENDED = "FARMER_SUSPENDED", "Suspend Farmer"
    FARMER_REINSTATED = "FARMER_REINSTATED", "Reinstate Farmer"
    CUSTOMER_DEACTIVATED = "CUSTOMER_DEACTIVATED", "Deactivate Customer"
    CUSTOMER_ACTIVATED = "CUSTOMER_ACTIVATED", "Activate Customer"
    PRODUCT_HIDDEN = "PRODUCT_HIDDEN", "Hide Product"
    PRODUCT_RESTORED = "PRODUCT_RESTORED", "Restore Product"
    # A legal takedown, which also cancels orders - kept apart from a plain hide so the
    # security log shows which of the two an admin actually did.
    PRODUCT_BLOCKED = "PRODUCT_BLOCKED", "Block Product"
    PRODUCT_UNBLOCKED = "PRODUCT_UNBLOCKED", "Unblock Product"
    REVIEW_HIDDEN = "REVIEW_HIDDEN", "Hide Review"
    REVIEW_RESTORED = "REVIEW_RESTORED", "Restore Review"
    # v1.8: market management by Admin (AD-15, AD-16, AD-17)
    MARKET_CREATED = "MARKET_CREATED", "Create Market"
    MARKET_UPDATED = "MARKET_UPDATED", "Update Market"
    MARKET_DEACTIVATED = "MARKET_DEACTIVATED", "Deactivate Market"
    MARKET_ACTIVATED = "MARKET_ACTIVATED", "Activate Market"
    # Admin edits a stall's or a shopper's contact details (AD-03, AD-10 PATCH).
    FARMER_UPDATED = "FARMER_UPDATED", "Update Farmer Profile"
    CUSTOMER_UPDATED = "CUSTOMER_UPDATED", "Update Customer Profile"
    # Housekeeping: unused sign-ups removed by the purge command.
    ACCOUNT_PURGED = "ACCOUNT_PURGED", "Purge Stale Accounts"
    CONTENT_FLAGGED = "CONTENT_FLAGGED", "Flag Content For Review"
    CONTENT_FLAG_RESOLVED = "CONTENT_FLAG_RESOLVED", "Resolve Flagged Content"


class AuditLog(CreatedAtModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_logs",
    )
    action = models.CharField(max_length=40, choices=AuditAction.choices)
    endpoint = models.CharField(max_length=255, null=True, blank=True)
    method = models.CharField(max_length=10, null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=255, null=True, blank=True)
    status_code = models.PositiveSmallIntegerField(null=True, blank=True)
    request_id = models.CharField(max_length=36, null=True, blank=True)
    details = models.JSONField(default=dict, encoder=DjangoJSONEncoder)

    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "created_at"], name="audit_action_created_idx"),
            models.Index(fields=["user", "created_at"], name="audit_user_created_idx"),
            models.Index(fields=["created_at"], name="audit_created_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.action} ({self.user_id})"


class FlagTarget(models.TextChoices):
    PRODUCT = "PRODUCT", "Product"
    FARMER_REVIEW = "FARMER_REVIEW", "Farmer Review"
    PRODUCT_REVIEW = "PRODUCT_REVIEW", "Product Review"
    FARMER = "FARMER", "Farmer"
    CUSTOMER = "CUSTOMER", "Customer"


class ModerationFlag(BaseModel):
    """Something an admin wants to come back to.

    Deliberately separate from hiding: hiding is a decision already taken, this is a note that
    a decision still has to be made. Without it the only way to work through the catalogue is
    to read all of it every time.
    """

    target_type = models.CharField(max_length=20, choices=FlagTarget.choices)
    # A plain integer rather than a generic relation: the three id spaces never mix, and this
    # stays a simple indexed lookup.
    target_id = models.PositiveBigIntegerField()
    note = models.CharField(max_length=500)
    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="flags_raised",
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True,
        related_name="flags_resolved",
    )
    resolution = models.CharField(max_length=500, null=True, blank=True)

    class Meta:
        db_table = "moderation_flags"
        indexes = [
            models.Index(fields=["target_type", "target_id"], name="flag_target_idx"),
            models.Index(fields=["resolved_at"], name="flag_resolved_idx"),
        ]
        # No conditional unique constraint here: MySQL has no partial indexes, so Django
        # would skip it silently and leave a rule nobody enforces. "One open flag per thing"
        # is checked in system.flags.raise_flag instead.

    def __str__(self) -> str:
        return f"{self.target_type} #{self.target_id}"
