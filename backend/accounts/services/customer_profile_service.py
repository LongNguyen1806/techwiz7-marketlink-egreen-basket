from django.db import IntegrityError, transaction

from accounts.models import CustomerProfile
from accounts.services.customer_registration_service import phone_taken, phone_taken_error


def update_customer_profile(*, user, data: dict) -> CustomerProfile:
    """CU-03: partial update of full_name / phone / address. `phone` arrives normalised by the serializer."""
    profile = user.customer_profile
    phone = data.get("phone")
    if phone and phone != profile.phone and phone_taken(phone, exclude_user_id=user.pk):
        raise phone_taken_error()

    for field, value in data.items():
        setattr(profile, field, value)
    try:
        with transaction.atomic():
            profile.save(update_fields=[*data, "updated_at"])
    except IntegrityError as exc:
        # Another customer took the number between the check and the save (D-028 UNIQUE index).
        if phone and phone_taken(phone, exclude_user_id=user.pk):
            raise phone_taken_error() from exc
        raise
    return profile
