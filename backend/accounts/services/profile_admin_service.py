from django.db import transaction

from accounts.models import CustomerProfile, FarmerProfile
from accounts.phone import normalize_phone
from marketlink_core.exceptions import BusinessValidationError

# What an admin may correct on someone else's behalf: the details a shopper or a stall would
# phone in to have fixed. Deliberately excluded, because they carry rules of their own that
# belong to the owner of the profile:
#   - operating_days  (D-031: dropping a day with open orders has to be refused, and the
#                      stall's pickup slots for that weekday switch off)
#   - address / latitude / longitude  (D-032: coordinates are looked up from the address)
#   - status          (that is approve / reject / suspend, AD-05 to AD-08)
FARMER_FIELDS = ("stall_name", "contact_person", "phone", "description", "order_cutoff_hours")
CUSTOMER_FIELDS = ("full_name", "phone", "address")


def _check_phone_is_free(*, phone: str, exclude_user_id: int, model) -> None:
    """One phone number per account, checked the same way registration checks it.

    Scoped to the one profile table, because that is where the UNIQUE index lives and what
    AU-01 / AU-02 enforce. Checking both tables here was stricter than the form that created
    the account: a number could be registered in each role, yet the admin could not correct
    a profile to it.

    The index would catch a duplicate anyway, but as an IntegrityError surfacing as a 500.
    Checking first turns it into a field error on the form.
    """
    taken = model.objects.filter(phone=phone).exclude(user_id=exclude_user_id).exists()
    if taken:
        raise BusinessValidationError(
            "That phone number already belongs to another account.",
            errors={"phone": ["This phone number is already in use."]},
        )


def _apply(profile, *, validated: dict, allowed: tuple[str, ...], actor) -> list[str]:
    changed = []
    for field in allowed:
        if field not in validated:
            continue
        value = validated[field]
        if field == "phone":
            value = normalize_phone(value)
            _check_phone_is_free(
                phone=value, exclude_user_id=profile.user_id, model=type(profile)
            )
        if getattr(profile, field) == value:
            continue
        setattr(profile, field, value)
        changed.append(field)

    if not changed:
        return []

    # The history row records who made the edit, so the audit trail does not read as if the
    # stall changed its own details.
    profile._history_user = actor
    profile._change_reason = "Edited by Admin"
    profile.save(update_fields=[*changed, "updated_at"])
    return changed


@transaction.atomic
def update_farmer_profile(*, farmer_id: int, validated: dict, actor) -> tuple[FarmerProfile, list[str]]:
    profile = FarmerProfile.objects.select_for_update().select_related("user").get(pk=farmer_id)
    return profile, _apply(profile, validated=validated, allowed=FARMER_FIELDS, actor=actor)


@transaction.atomic
def update_customer_profile(
    *, customer_id: int, validated: dict, actor
) -> tuple[CustomerProfile, list[str]]:
    profile = CustomerProfile.objects.select_for_update().select_related("user").get(pk=customer_id)
    return profile, _apply(profile, validated=validated, allowed=CUSTOMER_FIELDS, actor=actor)
