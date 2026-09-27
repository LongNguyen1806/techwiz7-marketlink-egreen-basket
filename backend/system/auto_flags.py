"""Flags the system raises by itself, so the follow-up queue is not only what an admin noticed.

Each rule only asks for a decision: nothing is hidden, locked or refused here, the admin
decides from the queue (the same stance as the AI listing review). One open flag per thing,
as with flags an admin raises; a second hit on something already queued adds nothing.

The hooks call these after the triggering change has been saved, and a failure here is
logged and swallowed: a review or a no-show must never fail because the queue could not be
written.
"""

import logging
from datetime import timedelta

from django.db.models import Count
from django.utils import timezone

from catalog.ai_review.wordlists import find_contact, find_profanity
from system.models import FlagTarget, ModerationFlag

logger = logging.getLogger("marketlink")

# Every note starts with this, so the queue and the log show the system raised the flag.
AUTO_PREFIX = "Auto:"
NOTE_MAX_LENGTH = 500

# "Not as described", as shoppers say it: several low ratings on one product in a short time.
LOW_RATING_MAX = 2
LOW_RATING_COUNT = 3
LOW_RATING_WINDOW_DAYS = 30
QUOTE_MAX_LENGTH = 120


def _raise_once(target_type: str, target_id: int, note: str) -> ModerationFlag | None:
    already_queued = ModerationFlag.objects.filter(
        target_type=target_type, target_id=target_id, resolved_at__isnull=True
    ).exists()
    if already_queued:
        return None
    # raised_by stays empty: the system raised it, and the note says so.
    return ModerationFlag.objects.create(
        target_type=target_type,
        target_id=target_id,
        note=f"{AUTO_PREFIX} {note}"[:NOTE_MAX_LENGTH],
        raised_by=None,
    )


def safely(check, *args, **kwargs) -> ModerationFlag | None:
    """Run a check from a hook; never let the queue break the action that triggered it."""
    try:
        return check(*args, **kwargs)
    except Exception:  # noqa: BLE001 - the queue is best effort, the action is not
        logger.exception("Automatic follow-up flag failed: %s", getattr(check, "__name__", check))
        return None


def text_problems(text: str | None) -> list[str]:
    """What is wrong with a piece of public text, in words an admin can act on."""
    text = text or ""
    problems = []
    swear = find_profanity(text)
    if swear:
        problems.append(f"offensive language ({', '.join(swear[:3])})")
    contact = find_contact(text)
    if contact:
        problems.append(f"contact details to trade off MarketLink ({', '.join(contact)})")
    return problems


def _review_target(review) -> str:
    from reviews.models import FarmerReview

    return FlagTarget.FARMER_REVIEW if isinstance(review, FarmerReview) else FlagTarget.PRODUCT_REVIEW


def check_review_text(review) -> ModerationFlag | None:
    """A shopper's review that swears or pushes a phone number / link."""
    problems = text_problems(review.comment)
    if not problems:
        return None
    return _raise_once(_review_target(review), review.pk, f"the review contains {'; '.join(problems)}.")


def check_reply_text(review) -> ModerationFlag | None:
    """The stall's public reply to a review, held to the same rules as the review."""
    problems = text_problems(review.reply)
    if not problems:
        return None
    return _raise_once(
        _review_target(review), review.pk, f"the stall's reply contains {'; '.join(problems)}."
    )


def check_product_low_ratings(product_id: int) -> ModerationFlag | None:
    """Several 1-2 star reviews on one product within a month: likely not as described."""
    from reviews.models import ProductReview

    since = timezone.now() - timedelta(days=LOW_RATING_WINDOW_DAYS)
    low = ProductReview.objects.filter(
        order_item__product_id=product_id,
        rating__lte=LOW_RATING_MAX,
        created_at__gte=since,
        is_hidden_by_admin=False,
    )
    count = low.count()
    if count < LOW_RATING_COUNT:
        return None
    latest = low.exclude(comment__isnull=True).exclude(comment="").order_by("-created_at")
    quote = latest.values_list("comment", flat=True).first()
    note = f"{count} ratings of {LOW_RATING_MAX} stars or less in the last {LOW_RATING_WINDOW_DAYS} days"
    if quote:
        shortened = quote if len(quote) <= QUOTE_MAX_LENGTH else quote[: QUOTE_MAX_LENGTH - 1] + "…"
        note += f'; latest: "{shortened}"'
    return _raise_once(FlagTarget.PRODUCT, product_id, note + ".")


def check_customer_no_shows(customer_id: int) -> ModerationFlag | None:
    """The shopper crossed the at-risk line the admin customer list uses (D-028)."""
    from orders.admin_selectors import (
        AT_RISK_STATUSES,
        at_risk_threshold,
        at_risk_window_days,
        at_risk_window_start,
    )
    from orders.models import Order

    count = Order.objects.filter(
        customer_id=customer_id,
        status__in=AT_RISK_STATUSES,
        created_at__gte=at_risk_window_start(),
    ).count()
    if count < at_risk_threshold():
        return None
    return _raise_once(
        FlagTarget.CUSTOMER,
        customer_id,
        f"{count} no-shows in the last {at_risk_window_days()} days (at risk).",
    )


def scan_existing() -> dict[str, int]:
    """Apply every rule to what is already in the database (the command and the seed)."""
    from orders.admin_selectors import AT_RISK_STATUSES, at_risk_threshold, at_risk_window_start
    from orders.models import Order
    from reviews.models import FarmerReview, ProductReview

    raised = {"reviews": 0, "replies": 0, "products": 0, "customers": 0}
    for model in (ProductReview, FarmerReview):
        for review in model.objects.filter(is_hidden_by_admin=False).iterator():
            if check_review_text(review):
                raised["reviews"] += 1
            elif review.reply and check_reply_text(review):
                raised["replies"] += 1

    since = timezone.now() - timedelta(days=LOW_RATING_WINDOW_DAYS)
    product_ids = (
        ProductReview.objects.filter(
            rating__lte=LOW_RATING_MAX, created_at__gte=since, is_hidden_by_admin=False
        )
        .values("order_item__product_id")
        .annotate(total=Count("id"))
        .filter(total__gte=LOW_RATING_COUNT)
        .values_list("order_item__product_id", flat=True)
    )
    for product_id in product_ids:
        if check_product_low_ratings(product_id):
            raised["products"] += 1

    customer_ids = (
        Order.objects.filter(status__in=AT_RISK_STATUSES, created_at__gte=at_risk_window_start())
        .values("customer_id")
        .annotate(total=Count("id"))
        .filter(total__gte=at_risk_threshold())
        .values_list("customer_id", flat=True)
    )
    for customer_id in customer_ids:
        if check_customer_no_shows(customer_id):
            raised["customers"] += 1
    return raised
