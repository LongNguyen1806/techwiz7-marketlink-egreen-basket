"""The follow-up queue.

Hiding content is a decision already made. A flag is the opposite: a note that a decision is
still owed, so the catalogue does not have to be read end to end every time.
"""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from marketlink_core.exceptions import BusinessValidationError, ErrorCode
from marketlink_core.shortcuts import get_or_404
from system.models import FlagTarget, ModerationFlag


def open_flags():
    return ModerationFlag.objects.filter(resolved_at__isnull=True).select_related(
        "raised_by"
    ).order_by("created_at", "id")


def list_flags(
    *, resolved: bool | None = False, target_type: str | None = None, q: str | None = None
):
    queryset = ModerationFlag.objects.select_related("raised_by", "resolved_by")
    if resolved is True:
        queryset = queryset.filter(resolved_at__isnull=False)
    elif resolved is False:
        queryset = queryset.filter(resolved_at__isnull=True)
    if target_type:
        queryset = queryset.filter(target_type=target_type)
    if q:
        term = q.strip()
        # A bare number is how an admin refers to a flagged thing ("#321"), so it also
        # matches the id of the target rather than only appearing inside the note.
        matches = Q(note__icontains=term) | Q(resolution__icontains=term)
        digits = term.lstrip("#")
        if digits.isdigit():
            matches |= Q(target_id=int(digits))
        queryset = queryset.filter(matches)
    # Oldest first: a queue is worked from the front, unlike a log.
    return queryset.order_by("resolved_at", "created_at", "id")


# Where an admin goes to look at the thing that was flagged, and what to call it there.
# Without this the queue names a row by number and leaves the admin to go and find it.
_TARGET_ROUTES = {
    FlagTarget.FARMER: "/admin/farmers/{id}",
    FlagTarget.CUSTOMER: "/admin/customers/{id}",
    FlagTarget.PRODUCT: "/admin/moderation?tab=products&product_id={id}",
    FlagTarget.PRODUCT_REVIEW: "/admin/moderation?tab=reviews&review_id={id}&review_type=PRODUCT",
    FlagTarget.FARMER_REVIEW: "/admin/moderation?tab=reviews&review_id={id}&review_type=FARMER",
}

PREVIEW_MAX_LENGTH = 120


def _shorten(text: str | None) -> str:
    text = (text or "").strip()
    if len(text) <= PREVIEW_MAX_LENGTH:
        return text
    return text[: PREVIEW_MAX_LENGTH - 1].rstrip() + "…"


def target_previews(flags) -> dict[tuple[str, int], str]:
    """A line of the flagged content per flag, looked up one query per kind.

    Batched deliberately: a page of twenty flags resolved one at a time is twenty queries,
    and the queue is the screen an admin keeps open.
    """
    from accounts.models import CustomerProfile, FarmerProfile
    from catalog.models import Product
    from reviews.models import FarmerReview, ProductReview

    wanted: dict[str, set[int]] = {}
    for flag in flags:
        wanted.setdefault(flag.target_type, set()).add(flag.target_id)

    previews: dict[tuple[str, int], str] = {}

    for pk, name, stall in Product.objects.filter(
        pk__in=wanted.get(FlagTarget.PRODUCT, ())
    ).values_list("pk", "name", "farmer__stall_name"):
        previews[(FlagTarget.PRODUCT, pk)] = _shorten(f"{name} — {stall}")

    for pk, name in FarmerProfile.objects.filter(
        pk__in=wanted.get(FlagTarget.FARMER, ())
    ).values_list("pk", "stall_name"):
        previews[(FlagTarget.FARMER, pk)] = _shorten(name)

    for pk, name in CustomerProfile.objects.filter(
        pk__in=wanted.get(FlagTarget.CUSTOMER, ())
    ).values_list("pk", "full_name"):
        previews[(FlagTarget.CUSTOMER, pk)] = _shorten(name)

    for kind, model in (
        (FlagTarget.PRODUCT_REVIEW, ProductReview),
        (FlagTarget.FARMER_REVIEW, FarmerReview),
    ):
        for pk, rating, comment in model.objects.filter(
            pk__in=wanted.get(kind, ())
        ).values_list("pk", "rating", "comment"):
            previews[(kind, pk)] = _shorten(f"{rating}★ {comment or ''}")

    return previews


def target_url(flag) -> str | None:
    route = _TARGET_ROUTES.get(flag.target_type)
    return route.format(id=flag.target_id) if route else None


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
