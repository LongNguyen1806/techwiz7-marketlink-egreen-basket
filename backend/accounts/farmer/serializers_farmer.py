import math
import re
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.models import FarmerProfile
from accounts.operating_days import normalize_operating_days
from accounts.phone import normalize_phone
from catalog.services.farmer_product import validate_image_upload
from marketlink_core.exceptions import BusinessValidationError

# §1.5: ^(0|\+84)(3|5|7|8|9)\d{8}$ checked after normalize_phone() turns +84 into 0 (D-028).
PHONE_PATTERN = re.compile(r"^0[35789]\d{8}$")
COORDINATE_STEP = Decimal("0.000001")


def validate_vn_phone(value: str, *, exclude_farmer_id: int | None = None) -> str:
    """Normalize, check the VN format and uniqueness among farmers (D-028)."""
    phone = normalize_phone(value)
    if not PHONE_PATTERN.match(phone):
        raise serializers.ValidationError("Invalid phone number")
    taken = FarmerProfile.objects.filter(phone=phone)
    if exclude_farmer_id is not None:
        taken = taken.exclude(pk=exclude_farmer_id)
    if taken.exists():
        raise serializers.ValidationError("This phone number is already registered.")
    return phone


def validate_operating_days_field(value: list[int]) -> list[int]:
    try:
        return normalize_operating_days(value)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(exc.message_dict["operating_days"]) from None


class FarmerProfileUpdateSerializer(serializers.Serializer):
    """FA-03 body (F-08). Every field is optional; email and status are never writable."""

    stall_name = serializers.CharField(min_length=2, max_length=100, required=False)
    contact_person = serializers.CharField(min_length=2, max_length=100, required=False)
    phone = serializers.CharField(max_length=20, required=False)
    address = serializers.CharField(min_length=5, max_length=255, required=False)
    operating_days = serializers.ListField(
        child=serializers.IntegerField(), allow_empty=True, required=False
    )
    description = serializers.CharField(
        max_length=1000, required=False, allow_blank=True, allow_null=True
    )
    image = serializers.FileField(required=False)
    # Only sent when the farmer drags the pin (D-032); rounded to 6 decimals for the column.
    latitude = serializers.FloatField(min_value=-90, max_value=90, required=False)
    longitude = serializers.FloatField(min_value=-180, max_value=180, required=False)
    order_cutoff_hours = serializers.IntegerField(min_value=1, max_value=72, required=False)

    def validate_phone(self, value: str) -> str:
        return validate_vn_phone(value, exclude_farmer_id=self.context.get("farmer_id"))

    def validate_operating_days(self, value: list[int]) -> list[int]:
        return validate_operating_days_field(value)

    def validate_description(self, value: str | None) -> str | None:
        return (value.strip() or None) if value is not None else None

    def validate_image(self, value: Any) -> Any:
        try:
            # The re-encoded copy is stored, never the uploaded bytes.
            return validate_image_upload(value)
        except BusinessValidationError as exc:
            raise serializers.ValidationError(exc.errors.get("image", [str(exc.detail)])) from None

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        has_lat, has_lng = "latitude" in attrs, "longitude" in attrs
        if has_lat != has_lng:
            missing = "longitude" if has_lat else "latitude"
            raise serializers.ValidationError(
                {missing: ["Latitude and longitude must be sent together."]}
            )
        for field in ("latitude", "longitude"):
            if field in attrs:
                if not math.isfinite(attrs[field]):
                    raise serializers.ValidationError({field: ["Invalid coordinates"]})
                attrs[field] = Decimal(str(attrs[field])).quantize(COORDINATE_STEP, rounding=ROUND_HALF_UP)
        return attrs
