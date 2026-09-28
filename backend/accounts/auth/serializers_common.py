import re

from django.contrib.auth.password_validation import validate_password as django_validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from accounts.auth.tokens import issue_tokens
from accounts.phone import normalize_phone
from markets.farmer_selectors import image_url

PHONE_PATTERN = r"^(0|\+84)(3|5|7|8|9)\d{8}$"


def clean_phone(value: str) -> str:
    phone = normalize_phone(value)
    if not re.fullmatch(PHONE_PATTERN, phone):
        raise serializers.ValidationError("Invalid phone number")
    return phone


def check_password_strength(value: str) -> str:
    if len(value) < 8 or not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value):
        raise serializers.ValidationError(
            "Password must be at least 8 characters and contain both letters and digits"
        )
    try:
        django_validate_password(value)
    except DjangoValidationError as exc:
        raise serializers.ValidationError(list(exc.messages)) from exc
    return value


class LoginWriteSerializer(serializers.Serializer):
    email = serializers.EmailField(max_length=100)
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_email(self, value: str) -> str:
        return value.strip().lower()


class RefreshTokenWriteSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class ChangePasswordWriteSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, trim_whitespace=False)
    confirm_password = serializers.CharField(write_only=True, trim_whitespace=False)

    def validate_new_password(self, value: str) -> str:
        return check_password_strength(value)

    def validate(self, attrs: dict) -> dict:
        if attrs["new_password"] != attrs.pop("confirm_password"):
            raise serializers.ValidationError({"confirm_password": ["Passwords do not match"]})
        return attrs


class MeReadSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    email = serializers.EmailField()
    role = serializers.CharField(source="role.code")
    display_name = serializers.SerializerMethodField()
    farmer_status = serializers.SerializerMethodField()
    avatar = serializers.SerializerMethodField()

    def get_avatar(self, user) -> str | None:
        """The customer's photo or the farmer's stall photo, for the account menu."""
        profile = getattr(user, "customer_profile", None) or getattr(user, "farmer_profile", None)
        return image_url(profile.image, self.context.get("request")) if profile is not None else None

    def get_display_name(self, user) -> str:
        profile = getattr(user, "customer_profile", None) or getattr(user, "farmer_profile", None)
        if profile is None:
            return "Administrator"
        return getattr(profile, "full_name", None) or profile.stall_name

    def get_farmer_status(self, user) -> str | None:
        farmer_profile = getattr(user, "farmer_profile", None)
        return farmer_profile.status if farmer_profile else None


def build_auth_payload(user, request=None) -> dict:
    return {**issue_tokens(user), "user": MeReadSerializer(user, context={"request": request}).data}
