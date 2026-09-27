from django.db import IntegrityError, transaction
from rest_framework import serializers

from accounts.exceptions import EmailExistsError
from accounts.models import CustomerProfile, CustomUser, Role
from marketlink_core.policies.roles import RoleCode

PHONE_TAKEN_MESSAGE = "This phone number is already registered."


def _email_exists_error() -> EmailExistsError:
    return EmailExistsError(errors={"email": [EmailExistsError.default_detail]})


def phone_taken_error() -> serializers.ValidationError:
    # Pass 4B v1.6 §4.1 / D-028: 400 VALIDATION_ERROR under the phone field (not a separate error code).
    return serializers.ValidationError({"phone": [PHONE_TAKEN_MESSAGE]})


def phone_taken(phone: str, *, exclude_user_id=None) -> bool:
    # Locked accounts keep their profile (D-017), so their number stays blocked too (D-028).
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
        # A concurrent sign-up won the race; the UNIQUE index tells us which value collided.
        if CustomUser.objects.filter(email=email).exists():
            raise _email_exists_error() from exc
        if phone_taken(phone):
            raise phone_taken_error() from exc
        raise
    return user
