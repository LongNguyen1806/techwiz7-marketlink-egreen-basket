from typing import Any

from rest_framework import serializers

from accounts.auth.serializers_common import clean_phone
from catalog.services.farmer_product import validate_image_upload
from marketlink_core.exceptions import BusinessValidationError
from markets.farmer_selectors import image_url


class CustomerProfileReadSerializer(serializers.Serializer):
    """Pass 4B §3.1 CustomerProfile."""

    full_name = serializers.CharField()
    phone = serializers.CharField()
    address = serializers.CharField()
    email = serializers.EmailField(source="user.email")
    image = serializers.SerializerMethodField()

    def get_image(self, profile) -> str | None:
        return image_url(profile.image, self.context.get("request"))


class CustomerProfileWriteSerializer(serializers.Serializer):
    """CU-03: same rules as sign-up (AU-01); email is read-only, so unknown keys are ignored.
    `image: null` removes the profile photo."""

    full_name = serializers.CharField(min_length=2, max_length=100, required=False)
    phone = serializers.CharField(max_length=20, required=False)
    address = serializers.CharField(min_length=5, max_length=255, required=False)
    image = serializers.FileField(required=False, allow_null=True)

    def validate_phone(self, value: str) -> str:
        return clean_phone(value)

    def validate_image(self, value: Any) -> Any:
        if value is None:
            return None
        try:
            return validate_image_upload(value)
        except BusinessValidationError as exc:
            raise serializers.ValidationError(exc.errors.get("image", [str(exc.detail)])) from None
