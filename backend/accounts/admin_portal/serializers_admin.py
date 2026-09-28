from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from accounts.auth.serializers_common import clean_phone
from accounts.services.no_show_lock import auto_lock_summary

from accounts.models import CustomerProfile, FarmerProfile

REASON_MIN_LENGTH = 5
REASON_MAX_LENGTH = 500


class AdminFarmerRowSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="user_id", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    date_joined = serializers.DateTimeField(source="user.date_joined", read_only=True)
    product_count = serializers.IntegerField(read_only=True, default=0)
    open_order_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = FarmerProfile
        fields = [
            "id",
            "stall_name",
            "contact_person",
            "phone",
            "email",
            "status",
            "date_joined",
            "product_count",
            "open_order_count",
        ]
        read_only_fields = fields


class AdminReasonSerializer(serializers.Serializer):
    reason = serializers.CharField(min_length=REASON_MIN_LENGTH, max_length=REASON_MAX_LENGTH)


class AdminCustomerRowSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(source="user_id", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    date_joined = serializers.DateTimeField(source="user.date_joined", read_only=True)
    is_active = serializers.BooleanField(source="user.is_active", read_only=True)
    total_orders = serializers.IntegerField(read_only=True, default=0)
    open_orders = serializers.IntegerField(read_only=True, default=0)
    no_show_count = serializers.IntegerField(read_only=True, default=0)
    at_risk = serializers.BooleanField(read_only=True, default=False)

    class Meta:
        model = CustomerProfile
        fields = [
            "id",
            "full_name",
            "email",
            "phone",
            "date_joined",
            "is_active",
            "deactivation_reason",
            "total_orders",
            "open_orders",
            "no_show_count",
            "at_risk",
        ]
        read_only_fields = fields


class AutoLockOrderSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    stall_name = serializers.CharField()
    market_name = serializers.CharField()
    pickup_date = serializers.DateField()
    total_amount = serializers.DecimalField(max_digits=10, decimal_places=2)


class AutoLockSerializer(serializers.Serializer):
    locked_at = serializers.DateTimeField()
    orders = AutoLockOrderSerializer(many=True)


class AdminCustomerDetailSerializer(AdminCustomerRowSerializer):
    recent_orders = serializers.SerializerMethodField()
    auto_lock = serializers.SerializerMethodField()

    class Meta(AdminCustomerRowSerializer.Meta):
        fields = [*AdminCustomerRowSerializer.Meta.fields, "address", "recent_orders", "auto_lock"]
        read_only_fields = fields

    def get_recent_orders(self, profile) -> list[dict]:
        return self.context.get("recent_orders", [])

    @extend_schema_field(AutoLockSerializer(allow_null=True))
    def get_auto_lock(self, profile) -> dict | None:
        summary = auto_lock_summary(profile.user_id)
        return AutoLockSerializer(summary).data if summary else None


class OpenOrderBreakdownSerializer(serializers.Serializer):
    PLACED = serializers.IntegerField()
    ACCEPTED = serializers.IntegerField()
    READY_FOR_PICKUP = serializers.IntegerField()
    total = serializers.IntegerField()


class SuspensionImpactSerializer(serializers.Serializer):
    open_orders = OpenOrderBreakdownSerializer()
    affected_customers = serializers.IntegerField()


class DeactivationImpactSerializer(serializers.Serializer):
    open_orders = OpenOrderBreakdownSerializer()
    affected_farmers = serializers.IntegerField()


class FarmerStatusHistorySerializer(serializers.Serializer):
    from_status = serializers.CharField(allow_null=True)
    to_status = serializers.CharField()
    reason = serializers.CharField(allow_null=True)
    changed_by = serializers.CharField(allow_null=True)
    changed_at = serializers.DateTimeField()


class FarmerOrderStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()
    completed = serializers.IntegerField()
    declined = serializers.IntegerField()
    expired = serializers.IntegerField()
    no_show = serializers.IntegerField()


class AdminFarmerEditSerializer(serializers.ModelSerializer):
    """AD-03 PATCH. Every field optional: the form sends only what the admin touched."""

    class Meta:
        model = FarmerProfile
        fields = ["stall_name", "contact_person", "phone", "description", "order_cutoff_hours"]
        extra_kwargs = {field: {"required": False} for field in fields}

    stall_name = serializers.CharField(min_length=2, max_length=100, required=False)
    contact_person = serializers.CharField(min_length=2, max_length=100, required=False)

    def validate_phone(self, value: str) -> str:
        if not value or not value.strip():
            raise serializers.ValidationError("A phone number is required.")
        return clean_phone(value)


class AdminCustomerEditSerializer(serializers.ModelSerializer):
    """AD-10 PATCH."""

    class Meta:
        model = CustomerProfile
        fields = ["full_name", "phone", "address"]
        extra_kwargs = {field: {"required": False} for field in fields}

    full_name = serializers.CharField(min_length=2, max_length=100, required=False)
    address = serializers.CharField(min_length=5, max_length=255, required=False)

    def validate_phone(self, value: str) -> str:
        return clean_phone(value)
