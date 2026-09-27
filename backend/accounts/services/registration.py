"""AU-02: farmer self-registration (FR-02, D-015, D-028, D-031, D-032)."""

import logging

from django.db import IntegrityError, transaction

from accounts.geocoding import geocode_address
from accounts.models import CustomUser, FarmerProfile, FarmerStatus, Role
from marketlink_core.exceptions import BusinessValidationError, ErrorCode
from marketlink_core.policies.roles import RoleCode

logger = logging.getLogger("marketlink")


def _email_exists_error() -> BusinessValidationError:
    return BusinessValidationError(
        "This email is already registered.",
        code=ErrorCode.EMAIL_EXISTS,
        errors={"email": ["This email is already registered."]},
    )


def _phone_taken_error() -> BusinessValidationError:
    return BusinessValidationError(
        "Invalid input. Please check the highlighted fields.",
        errors={"phone": ["This phone number is already registered."]},
    )


def register_farmer(
    *,
    email: str,
    password: str,
    stall_name: str,
    contact_person: str,
    phone: str,
    address: str,
    operating_days: list[int],
) -> tuple[CustomUser, FarmerProfile]:
    """Create the user and a PENDING profile in one transaction, then geocode the address.

    Emails of locked accounts stay taken (D-028: locking is the blacklist).
    """
    role = Role.objects.get(code=RoleCode.FARMER)
    try:
        with transaction.atomic():
            if CustomUser.objects.filter(email=email).exists():
                raise _email_exists_error()
            user = CustomUser.objects.create_user(email=email, password=password, role=role)
            profile = FarmerProfile.objects.create(
                user=user,
                stall_name=stall_name,
                contact_person=contact_person,
                phone=phone,
                address=address,
                operating_days=operating_days,
                status=FarmerStatus.PENDING,
            )
    except IntegrityError as exc:
        # Two sign-ups with the same email / phone at once: the UNIQUE keys are the last guard.
        message = str(exc).lower()
        if "email" in message:
            raise _email_exists_error() from exc
        if "phone" in message:
            raise _phone_taken_error() from exc
        raise

    # D-032: outside the transaction; a failed lookup leaves the coordinates empty and never
    # breaks the registration (F-08 then shows "Location not found").
    try:
        coordinates = geocode_address(address)
    except Exception:  # noqa: BLE001 - geocoding is best effort
        logger.exception("Geocoding after farmer registration failed")
        coordinates = None
    if coordinates:
        profile.latitude, profile.longitude = coordinates
        profile.save(update_fields=["latitude", "longitude", "updated_at"])
    return user, profile
