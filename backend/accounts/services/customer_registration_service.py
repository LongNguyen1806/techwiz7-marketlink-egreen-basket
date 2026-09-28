from django.db import IntegrityError, transaction
from rest_framework import serializers

from accounts.exceptions import EmailExistsError
from accounts.models import CustomerProfile, CustomUser, Role
from marketlink_core.policies.roles import RoleCode

PHONE_TAKEN_MESSAGE = "This phone number is already registered."


def _email_exists_error() -> EmailExistsError:
    return EmailExistsError(errors={"email": [EmailExistsError.default_detail]})


def phone_taken_error() -> serializers.ValidationError:
    return serializers.ValidationError({"phone": [PHONE_TAKEN_MESSAGE]})


def phone_taken(phone: str, *, exclude_user_id=None) -> bool:
    return CustomerProfile.objects.filter(phone=phone).exclude(user_id=exclude_user_id).exists()


def register_customer(*, email: str, password: str, full_name: str, phone: str, address: str) -> CustomUser:
    """`phone` arrives normalised by the serializer (accounts.phone.normalize_phone)."""
    if CustomUser.objects.filter(email=email).exists():
        raise _email_exists_error()
    if phone_taken(phone):
        raise phone_taken_error()

    role = Role.objects.get(code=RoleCode.CUSTOMER)
    try:
        with transaction.atomic():
            user = CustomUser.objects.create_user(email=email, password=password, role=role)
            CustomerProfile.objects.create(user=user, full_name=full_name, phone=phone, address=address)
    except IntegrityError as exc:
        if CustomUser.objects.filter(email=email).exists():
            raise _email_exists_error() from exc
        if phone_taken(phone):
            raise phone_taken_error() from exc
        raise
    return user
