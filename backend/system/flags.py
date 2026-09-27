"""The follow-up queue.

Hiding content is a decision already made. A flag is the opposite: a note that a decision is
still owed, so the catalogue does not have to be read end to end every time.
"""

from django.db import transaction
from django.utils import timezone

from marketlink_core.exceptions import BusinessValidationError, ErrorCode
from marketlink_core.shortcuts import get_or_404
from system.models import ModerationFlag


def open_flags():
    return ModerationFlag.objects.filter(resolved_at__isnull=True).select_related(
        "raised_by"
    ).order_by("created_at", "id")


def list_flags(*, resolved: bool | None = False, target_type: str | None = None):
    queryset = ModerationFlag.objects.select_related("raised_by", "resolved_by")
    if resolved is True:
        queryset = queryset.filter(resolved_at__isnull=False)
    elif resolved is False:
        queryset = queryset.filter(resolved_at__isnull=True)
    if target_type:
        queryset = queryset.filter(target_type=target_type)
    # Oldest first: a queue is worked from the front, unlike a log.
    return queryset.order_by("resolved_at", "created_at", "id")


@transaction.atomic
def raise_flag(*, target_type: str, target_id: int, note: str, actor) -> ModerationFlag:
    # Checked here rather than by a database constraint: the rule is "one *open* flag per
    # thing", and MySQL has no partial unique index to express that.
    already_queued = ModerationFlag.objects.filter(
        target_type=target_type, target_id=target_id, resolved_at__isnull=True
    ).exists()
    if already_queued:
        raise BusinessValidationError(
            "This is already in the queue.",
            code=ErrorCode.RESOURCE_IN_USE,
        )
    return ModerationFlag.objects.create(
        target_type=target_type, target_id=target_id, note=note, raised_by=actor
    )


@transaction.atomic
def resolve_flag(*, flag_id: int, resolution: str, actor) -> ModerationFlag:
    flag = get_or_404(
        ModerationFlag.objects.select_for_update(), message="Flag not found.", pk=flag_id
    )
    if flag.resolved_at is not None:
        raise BusinessValidationError(
            "This was already dealt with.",
            code=ErrorCode.INVALID_STATUS_TRANSITION,
        )
    flag.resolved_at = timezone.now()
    flag.resolved_by = actor
    flag.resolution = resolution
    flag.save(update_fields=["resolved_at", "resolved_by", "resolution", "updated_at"])
    return flag
