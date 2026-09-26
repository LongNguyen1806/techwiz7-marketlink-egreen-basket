from rest_framework import serializers

from accounts.admin_portal.serializers_admin import AdminFarmerRowSerializer
from accounts.models import CustomUser
from orders.models import OrderStatus
from system.models import AuditLog


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


class OrdersByStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=OrderStatus.choices)
    count = serializers.IntegerField()


class DashboardSerializer(serializers.Serializer):
    totals = DashboardTotalsSerializer()
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
