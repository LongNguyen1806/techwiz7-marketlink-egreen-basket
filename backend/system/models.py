from django.conf import settings
from django.core.serializers.json import DjangoJSONEncoder
from django.db import models

from marketlink_core.models import CreatedAtModel


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
