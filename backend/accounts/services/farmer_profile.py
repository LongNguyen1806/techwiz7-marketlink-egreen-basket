"""FA-03: update the farmer's own stall profile (D-031 operating days, D-032 coordinates)."""

from dataclasses import dataclass
from typing import Any

from django.db import IntegrityError, transaction
from django.utils import timezone

from accounts.geocoding import geocode_address
from accounts.models import FarmerProfile
from marketlink_core.exceptions import BusinessValidationError, ErrorCode, UnprocessableEntityError
from marketlink_core.history import save_with_history
from markets.models import PickupSlot
from orders.models import OPEN_STATUSES, Order
from orders.services.expiry import expire_overdue_orders
from orders.services.fsm import run_with_retry_if_top_level

ALL_DAYS = frozenset(range(1, 8))

# Columns FA-03 may write; the save lists exactly the changed ones.
UPDATABLE_FIELDS = (
    "stall_name",
    "contact_person",
    "phone",
    "address",
    "operating_days",
    "description",
    "image",
    "latitude",
    "longitude",
    "order_cutoff_hours",
)


@dataclass(frozen=True)
class ProfileUpdateResult:
    profile: FarmerProfile
    # Set only when operating days were removed (FA-03 response adds deactivated_slot_count).
    deactivated_slot_count: int | None = None


def _phone_taken_error() -> BusinessValidationError:
    return BusinessValidationError(
        "Invalid input. Please check the highlighted fields.",
        errors={"phone": ["This phone number is already registered."]},
    )


def _resolve_coordinates(farmer_id: int, data: dict[str, Any]) -> None:
    """D-032: a new address is geocoded outside the transaction unless the farmer dragged the pin."""
    if "address" not in data or "latitude" in data:
        return
    current = FarmerProfile.objects.filter(pk=farmer_id).values_list("address", flat=True).first()
    if data["address"] == current:
        return
    coordinates = geocode_address(data["address"])
    data["latitude"], data["longitude"] = coordinates if coordinates else (None, None)


def update_farmer_profile(*, farmer_id: int, data: dict[str, Any]) -> ProfileUpdateResult:
    data = dict(data)
    _resolve_coordinates(farmer_id, data)
    if "operating_days" in data:
        # Orders whose pickup already started must not block removing a day (A-005 lazy sweep).
        expire_overdue_orders(farmer_id=farmer_id)

    def _execute() -> ProfileUpdateResult:
        with transaction.atomic():
            # Lock order (§5.2): farmer_profiles -> orders (read) -> pickup_slots.
            profile = (
                FarmerProfile.objects.select_for_update(of=("self",))
                .select_related("user")
                .get(pk=farmer_id)
            )
            deactivated = None
            if "operating_days" in data and data["operating_days"] != profile.operating_days:
                # Enforce on every day that is no longer an operating day (not only the ones just
                # removed), so rows created before D-031 get consistent slots too.
                off_days = sorted(ALL_DAYS - set(data["operating_days"]))
                count = _deactivate_off_days(farmer_id=farmer_id, off_days=off_days) if off_days else 0
                if set(profile.operating_days or []) - set(data["operating_days"]) or count:
                    deactivated = count

            old_image_name = profile.image.name if "image" in data and profile.image else None
            if "image" in data:
                data["image"].seek(0)  # a deadlock retry must upload the whole file again
            changed = [field for field in UPDATABLE_FIELDS if field in data]
            for field in changed:
                setattr(profile, field, data[field])
            if changed:
                profile.save(update_fields=[*changed, "updated_at"])

            if old_image_name and old_image_name != profile.image.name:
                storage = profile.image.storage
                transaction.on_commit(lambda: storage.delete(old_image_name))
        return ProfileUpdateResult(profile=profile, deactivated_slot_count=deactivated)

    try:
        return run_with_retry_if_top_level(_execute)
    except IntegrityError as exc:
        # Two requests took the same phone at once: the UNIQUE key (D-028) is the last guard.
        if "phone" in str(exc).lower():
            raise _phone_taken_error() from exc
        raise


def _deactivate_off_days(*, farmer_id: int, off_days: list[int]) -> int:
    """D-031: block while open orders fall on a non-operating weekday, else switch those slots off."""
    blocking = list(
        Order.objects.filter(
            farmer_id=farmer_id,
            status__in=OPEN_STATUSES,
            pickup_date__gte=timezone.localdate(),
            pickup_date__iso_week_day__in=off_days,
        )
        .order_by("id")
        .values_list("id", flat=True)
    )
    if blocking:
        raise UnprocessableEntityError(
            "Some open orders are picked up on the days you want to remove. "
            "Please handle those orders first.",
            code=ErrorCode.RESOURCE_IN_USE,
            errors={"order_ids": blocking},
        )
    # One save per slot (not QuerySet.update) so each switched-off slot gets a history row (v1.8).
    slots = list(
        PickupSlot.objects.select_for_update(of=("self",))
        .filter(farmer_market__farmer_id=farmer_id, day_of_week__in=off_days, is_active=True)
        .order_by("id")
    )
    for slot in slots:
        slot.is_active = False
        save_with_history(
            slot,
            update_fields=["is_active", "updated_at"],
            reason=f"Switched off: day {slot.day_of_week} is no longer an operating day",
        )
    return len(slots)
