from typing import Any

from django.core.exceptions import ValidationError

MIN_DAY = 1
MAX_DAY = 7


def normalize_operating_days(value: Any) -> list[int]:
    """Return the sorted list of ISO weekdays, or raise ValidationError.

    Rules: a list with at least 1 item, each an integer 1-7 (not bool, not "2"), no duplicates.
    """
    if not isinstance(value, list) or not value:
        raise ValidationError(
            {"operating_days": ["Select at least one operating day."]}, code="required"
        )
    for day in value:
        if isinstance(day, bool) or not isinstance(day, int) or not MIN_DAY <= day <= MAX_DAY:
            raise ValidationError(
                {"operating_days": [f"Each operating day must be an integer from {MIN_DAY} to {MAX_DAY}."]},
                code="invalid",
            )
    if len(set(value)) != len(value):
        raise ValidationError(
            {"operating_days": ["Operating days must not contain duplicates."]}, code="duplicate"
        )
    return sorted(value)
