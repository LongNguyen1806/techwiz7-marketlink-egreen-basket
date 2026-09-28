from django.db import IntegrityError, transaction

from accounts.models import CustomerProfile
from accounts.services.customer_registration_service import phone_taken, phone_taken_error


def update_customer_profile(*, user, data: dict) -> CustomerProfile:
    """CU-03: partial update of full_name / phone / address / image. `phone` arrives normalised by
    the serializer; `image: None` removes the photo. A replaced or removed photo file is deleted
    once the change is committed, as for the farmer's stall photo."""
    profile = user.customer_profile
    phone = data.get("phone")
    if phone and phone != profile.phone and phone_taken(phone, exclude_user_id=user.pk):
        raise phone_taken_error()

    old_image_name = profile.image.name if "image" in data and profile.image else None
    if data.get("image"):
        data["image"].seek(0)
    for field, value in data.items():
        setattr(profile, field, value)
    try:
        with transaction.atomic():
            profile.save(update_fields=[*data, "updated_at"])
            if old_image_name and old_image_name != profile.image.name:
                storage = profile.image.storage
                transaction.on_commit(lambda: storage.delete(old_image_name))
    except IntegrityError as exc:
        if phone and phone_taken(phone, exclude_user_id=user.pk):
            raise phone_taken_error() from exc
        raise
    return profile
