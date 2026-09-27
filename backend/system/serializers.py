from rest_framework import serializers

from accounts.admin_portal.serializers_admin import AdminFarmerRowSerializer
from accounts.models import CustomUser
from orders.models import OrderStatus
from system.models import AuditLog, FlagTarget, ModerationFlag
from system.flags import target_url


class AuditLogActorSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ["id", "email"]
        read_only_fields = fields


class AuditLogReadSerializer(serializers.ModelSerializer):
    user = AuditLogActorSerializer(read_only=True)

    class Meta:
        model = AuditLog
        fields = [
            "id",
            "user",
            "action",
            "endpoint",
            "method",
            "ip_address",
            "user_agent",
            "status_code",
            "request_id",
            "details",
            "created_at",
        ]
        read_only_fields = fields


class DashboardTotalsSerializer(serializers.Serializer):
    farmers = serializers.IntegerField()
    farmers_pending = serializers.IntegerField()
    customers = serializers.IntegerField()
    markets_active = serializers.IntegerField()
    orders = serializers.IntegerField()


class OrdersByDaySerializer(serializers.Serializer):
    date = serializers.DateField()
    count = serializers.IntegerField()


class OrdersByMonthSerializer(serializers.Serializer):
    """One calendar month of the orders chart, which the dashboard pages through."""

    month = serializers.CharField()
    total = serializers.IntegerField()
    days = OrdersByDaySerializer(many=True)


class OrdersByStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=OrderStatus.choices)
    count = serializers.IntegerField()


class NeedsAttentionSerializer(serializers.Serializer):
    """Counts an admin can act on, as opposed to counts that merely describe the platform."""

    stalls_awaiting_approval = serializers.IntegerField()
    products_awaiting_approval = serializers.IntegerField()
    flags_open = serializers.IntegerField()
    customers_at_risk = serializers.IntegerField()
    hidden_products = serializers.IntegerField()
    markets_closed = serializers.IntegerField()


class DashboardSerializer(serializers.Serializer):
    totals = DashboardTotalsSerializer()
    needs_attention = NeedsAttentionSerializer()
    orders_by_day = OrdersByDaySerializer(many=True)
    orders_by_status = OrdersByStatusSerializer(many=True)
    pending_farmers = AdminFarmerRowSerializer(many=True)


class RevenueByMarketSerializer(serializers.Serializer):
    market_id = serializers.IntegerField()
    market_name = serializers.CharField()
    completed_orders = serializers.IntegerField()
    revenue = serializers.CharField()


class TopFarmerSerializer(serializers.Serializer):
    farmer_id = serializers.IntegerField()
    stall_name = serializers.CharField()
    completed_orders = serializers.IntegerField()
    revenue = serializers.CharField()
    rating_avg = serializers.FloatField(allow_null=True)


class ReportSummarySerializer(serializers.Serializer):
    orders_by_status = OrdersByStatusSerializer(many=True)
    revenue_by_market = RevenueByMarketSerializer(many=True)
    top_farmers = TopFarmerSerializer(many=True)


CHANGE_LOG_TYPES = ["CREATED", "UPDATED", "DELETED"]


class ChangeSerializer(serializers.Serializer):
    """One field of one revision: what it was, what it became."""

    field = serializers.CharField()
    old = serializers.JSONField(allow_null=True)
    new = serializers.JSONField(allow_null=True)


class ChangeLogEntrySerializer(serializers.Serializer):
    """A revision of a tracked record, read from its django-simple-history table (v1.8).

    This is the audit *trail* - how one record changed over time. The audit *log*
    (AuditLogReadSerializer above) is the separate security record of admin actions.
    """

    history_id = serializers.IntegerField()
    # Exposed as change_type, not type: a bare "type" collides with the other choice fields
    # of that name when the schema names its enums, and it reads better here anyway.
    change_type = serializers.ChoiceField(source="type", choices=CHANGE_LOG_TYPES)
    date = serializers.CharField()
    user = AuditLogActorSerializer(allow_null=True)
    reason = serializers.CharField(allow_null=True)
    request_id = serializers.CharField(allow_null=True)
    changes = ChangeSerializer(many=True)


class ModerationFlagReadSerializer(serializers.ModelSerializer):
    raised_by = AuditLogActorSerializer(read_only=True)
    resolved_by = AuditLogActorSerializer(read_only=True)
    # Where to go and look, and a line of what is there. A queue that only gives a number
    # makes the admin hunt for the thing before every decision.
    target_url = serializers.SerializerMethodField()
    target_preview = serializers.SerializerMethodField()

    class Meta:
        model = ModerationFlag
        fields = [
            "id", "target_type", "target_id", "target_url", "target_preview", "note",
            "raised_by", "created_at", "resolved_at", "resolved_by", "resolution",
        ]
        read_only_fields = fields

    def get_target_url(self, flag) -> str | None:
        return target_url(flag)

    def get_target_preview(self, flag) -> str | None:
        # Missing when the flagged row has since been deleted, which the screen says out loud.
        return self.context.get("target_previews", {}).get((flag.target_type, flag.target_id))


class ModerationFlagWriteSerializer(serializers.Serializer):
    target_type = serializers.ChoiceField(choices=FlagTarget.choices)
    target_id = serializers.IntegerField(min_value=1)
    note = serializers.CharField(min_length=5, max_length=500)


class FlagResolutionSerializer(serializers.Serializer):
    resolution = serializers.CharField(min_length=5, max_length=500)


class AdminSettingsSerializer(serializers.Serializer):
    """The operating limits, with the plain-language name each one goes by on screen."""

    booking_horizon_days = serializers.IntegerField()
    max_placed_orders_per_customer = serializers.IntegerField()
    max_upload_mb = serializers.IntegerField()
    at_risk_threshold = serializers.IntegerField()
    at_risk_window_days = serializers.IntegerField()


