from typing import Any

from rest_framework import serializers

TIME_FORMATS = ["%H:%M"]  # §1.5: HH:mm


class _StallLabelMixin(serializers.Serializer):
    # D-026: "Stall location in market", required, <= 100 characters.
    stall_label = serializers.CharField(min_length=1, max_length=100)


class JoinMarketFarmerSerializer(_StallLabelMixin):
    """FA-05 body."""

    market_id = serializers.IntegerField(min_value=1)


class UpdateStallLabelFarmerSerializer(_StallLabelMixin):
    """FA-06 body."""


class CreatePickupSlotFarmerSerializer(serializers.Serializer):
    """FA-08 body."""

    farmer_market_id = serializers.IntegerField(min_value=1)
    day_of_week = serializers.IntegerField(min_value=1, max_value=7)
    start_time = serializers.TimeField(input_formats=TIME_FORMATS)
    end_time = serializers.TimeField(input_formats=TIME_FORMATS)


class UpdatePickupSlotFarmerSerializer(serializers.Serializer):
    """FA-09 body (every field optional)."""

    day_of_week = serializers.IntegerField(min_value=1, max_value=7, required=False)
    start_time = serializers.TimeField(input_formats=TIME_FORMATS, required=False)
    end_time = serializers.TimeField(input_formats=TIME_FORMATS, required=False)
    is_active = serializers.BooleanField(required=False)


class CreateClosureFarmerSerializer(serializers.Serializer):
    """FA-32 body."""

    start_date = serializers.DateField()
    end_date = serializers.DateField()
    reason = serializers.CharField(max_length=200, required=False, allow_blank=True, allow_null=True)

    def validate_reason(self, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        attrs.setdefault("reason", None)
        return attrs
