"""Runs both layers over a listing, stores the advice, and acts on the clear cases.

#6: a new or re-submitted listing the AI passes goes on sale at once; one it thinks breaks
the rules stays off sale and goes to the follow-up queue; anything else (unsure, or the AI
could not be asked) waits for an admin as before. Every automatic decision is listed in
AI decisions (#8), where an admin can confirm or undo it. Hiding, blocking and account
actions stay with an administrator.
"""

import hashlib
import logging
import mimetypes
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

from django.conf import settings
from django.db import close_old_connections, transaction
from django.utils import timezone

from accounts.models import CustomUser, RoleCode
from catalog.ai_review import gemini, rules
from catalog.ai_review.types import Finding, ListingInput, risk_score, verdict_for
from catalog.models import (
    AIAutoAction,
    AIReviewKind,
    AIVerdict,
    Category,
    Product,
    ProductAIReview,
    ReviewStatus,
)
from notifications.messages import render_notification
from notifications.models import Notification, NotificationType
from notifications.services import notify
from system.models import FlagTarget, ModerationFlag

logger = logging.getLogger("marketlink")

_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="marketlink-ai-review")
UNAVAILABLE_RETRY_AFTER = timedelta(minutes=10)
FLAG_NOTE_PREFIX = "AI review:"


def _read_image(product: Product) -> tuple[bytes | None, str | None]:
    if not product.image:
        return None, None
    try:
        with product.image.open("rb") as handle:
            data = handle.read()
    except (OSError, ValueError):
        logger.warning("AI review could not read the image of product %s", product.pk)
        return None, None
    mime = mimetypes.guess_type(product.image.name)[0] or "image/jpeg"
    return data, mime


def listing_from_product(product: Product, *, with_image: bool = True) -> ListingInput:
    image, mime = _read_image(product) if with_image else (None, None)
    return ListingInput(
        name=product.name,
        description=product.description or "",
        category_id=product.category_id,
        category_name=product.category.name if product.category_id else "",
        unit=product.unit,
        price=product.price,
        stock_quantity=product.stock_quantity,
        min_per_order=product.min_per_order,
        max_per_order=product.max_per_order,
        product_id=product.pk,
        image_bytes=image,
        image_mime=mime,
    )


def content_hash(listing: ListingInput, kind: str) -> str:
    """What the advice is about. The same content is never reviewed (or paid for) twice."""
    if kind == AIReviewKind.WEEKLY_IMAGE:
        parts = [listing.name, str(listing.category_id), hashlib.sha256(listing.image_bytes or b"").hexdigest()]
    else:
        parts = [
            listing.name, listing.description, str(listing.category_id), listing.unit, str(listing.price),
            str(listing.stock_quantity), str(listing.min_per_order), str(listing.max_per_order),
            hashlib.sha256(listing.image_bytes or b"").hexdigest(),
        ]
    return hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()


def _category_names() -> list[str]:
    return list(Category.objects.filter(is_active=True).order_by("display_order", "name").values_list("name", flat=True))


def evaluate(listing: ListingInput, *, kind: str = AIReviewKind.LISTING, use_ai: bool = True) -> dict:
    """Both layers over one listing, without saving anything (used by review, precheck, eval)."""
    started = time.monotonic()
    findings: list[Finding] = [] if kind == AIReviewKind.WEEKLY_IMAGE else rules.run_rules(listing)
    ai_error, ai_used, suggested, summary, model_name = None, False, None, "", ""
    if use_ai and kind == AIReviewKind.LISTING and verdict_for(findings) == AIVerdict.LIKELY_VIOLATION:
        use_ai = False
        ai_error = "the rule checks already found a likely violation, so the AI was not asked (saves quota)"
    if use_ai:
        try:
            result = gemini.ask_model(listing, _category_names(), image_only=kind == AIReviewKind.WEEKLY_IMAGE)
            findings.extend(result.findings)
            ai_used, suggested, summary, model_name = True, result.suggested_category, result.summary, result.model_name
        except gemini.AIUnavailable as exc:
            ai_error = str(exc)

    verdict = verdict_for(findings)
    if not ai_used and use_ai and verdict == AIVerdict.PASS:
        verdict = AIVerdict.UNAVAILABLE
    if not summary:
        summary = _summary(findings, verdict)
    return {
        "verdict": verdict,
        "risk_score": risk_score(findings),
        "findings": findings,
        "summary": summary,
        "suggested_category": suggested,
        "ai_used": ai_used,
        "ai_error": ai_error,
        "model_name": model_name,
        "duration_ms": int((time.monotonic() - started) * 1000),
    }


def _summary(findings: list[Finding], verdict: str) -> str:
    if not findings:
        return "No problems found by the rule checks." if verdict == AIVerdict.UNAVAILABLE else "No problems found."
    worst = sorted(findings, key=lambda f: {"HIGH": 0, "MEDIUM": 1, "LOW": 2}.get(f.severity, 3))[0]
    more = f" (+{len(findings) - 1} more)" if len(findings) > 1 else ""
    return f"{worst.message}{more}"[:500]


def latest_review(product_id: int, kind: str = AIReviewKind.LISTING) -> ProductAIReview | None:
    return ProductAIReview.objects.filter(product_id=product_id, kind=kind).order_by("-created_at", "-id").first()


def review_product(product_id: int, *, kind: str = AIReviewKind.LISTING, force: bool = False) -> ProductAIReview | None:
    """Review one listing and store the advice. Returns None when there is nothing to review."""
    product = Product.objects.select_related("category", "farmer").filter(pk=product_id).first()
    if product is None or product.is_archived:
        return None
    listing = listing_from_product(product)
    if kind == AIReviewKind.WEEKLY_IMAGE and not listing.image_bytes:
        return None
    digest = content_hash(listing, kind)

    previous = latest_review(product_id, kind)
    if not force and previous is not None and previous.content_hash == digest:
        if previous.verdict != AIVerdict.UNAVAILABLE or previous.created_at > timezone.now() - UNAVAILABLE_RETRY_AFTER:
            return previous

    result = evaluate(listing, kind=kind)
    suggested = None
    if result["suggested_category"] and result["suggested_category"] != listing.category_name:
        suggested = Category.objects.filter(name=result["suggested_category"]).first()
    review = ProductAIReview.objects.create(
        product=product,
        kind=kind,
        content_hash=digest,
        verdict=result["verdict"],
        risk_score=result["risk_score"],
        findings=[finding.as_dict() for finding in result["findings"]],
        summary=result["summary"],
        suggested_category=suggested,
        ai_used=result["ai_used"],
        ai_error=result["ai_error"],
        model_name=result["model_name"],
        prompt_version=gemini.PROMPT_VERSION if result["ai_used"] else "",
        rules_version=rules.RULES_VERSION if kind == AIReviewKind.LISTING else "",
        duration_ms=result["duration_ms"],
    )
    _alert_admins(product, review)
    if kind == AIReviewKind.LISTING:
        _act_on_listing(product.pk, review)
    return review


def _act_on_listing(product_id: int, review: ProductAIReview) -> None:
    """#6: approve a clean pass, hold a likely violation, leave the rest to an admin."""
    if review.verdict == AIVerdict.LIKELY_VIOLATION:
        review.auto_action, review.auto_action_at = AIAutoAction.HELD, timezone.now()
        review.save(update_fields=["auto_action", "auto_action_at"])
        return
    if review.verdict != AIVerdict.PASS or not settings.AI_AUTO_APPROVE:
        return
    with transaction.atomic():
        product = (
            Product.objects.select_for_update()
            .select_related("farmer__user")
            .filter(pk=product_id, review_status=ReviewStatus.PENDING, is_archived=False)
            .first()
        )
        if product is None:
            return
        now = timezone.now()
        product.review_status = ReviewStatus.APPROVED
        product.review_note = None
        product.reviewed_at = now
        product.reviewed_by = None
        product.save(
            update_fields=["review_status", "review_note", "reviewed_at", "reviewed_by", "updated_at"]
        )
        review.auto_action, review.auto_action_at = AIAutoAction.APPROVED, now
        review.save(update_fields=["auto_action", "auto_action_at"])
        notify(
            recipient=product.farmer.user,
            event_type=NotificationType.PRODUCT_APPROVED,
            context={"product_name": product.name},
        )
        _tell_admins_of_approval(product)


def unchecked_auto_approvals() -> int:
    return ProductAIReview.objects.filter(
        auto_action=AIAutoAction.APPROVED, admin_checked_at__isnull=True
    ).count()


def _tell_admins_of_approval(product: Product) -> None:
    """#8: one running notice per admin, rewritten as approvals come in, not one per listing."""
    context = {
        "count": unchecked_auto_approvals(),
        "product_name": product.name,
        "stall_name": product.farmer.stall_name,
    }
    title, message, target_url = render_notification(NotificationType.AI_AUTO_APPROVED, context)
    for admin in CustomUser.objects.filter(role__code=RoleCode.ADMIN, is_active=True):
        unread = Notification.objects.filter(
            recipient=admin, type=NotificationType.AI_AUTO_APPROVED, is_read=False
        ).first()
        if unread is None:
            notify(recipient=admin, event_type=NotificationType.AI_AUTO_APPROVED, context=context)
        else:
            Notification.objects.filter(pk=unread.pk).update(
                title=title, message=message, target_url=target_url, created_at=timezone.now()
            )


def _alert_admins(product: Product, review: ProductAIReview) -> None:
    """A likely violation, or anything the weekly photo check dislikes, goes to the admins' queue."""
    worth_alert = review.verdict == AIVerdict.LIKELY_VIOLATION or (
        review.kind == AIReviewKind.WEEKLY_IMAGE and review.verdict == AIVerdict.NEEDS_REVIEW
    )
    if not worth_alert:
        return
    already_open = ModerationFlag.objects.filter(
        target_type=FlagTarget.PRODUCT, target_id=product.pk, resolved_at__isnull=True
    ).exists()
    if not already_open:
        ModerationFlag.objects.create(
            target_type=FlagTarget.PRODUCT,
            target_id=product.pk,
            note=f"{FLAG_NOTE_PREFIX} {review.summary}"[:500],
            raised_by=None,
        )
    label = "Weekly photo check" if review.kind == AIReviewKind.WEEKLY_IMAGE else "New listing"
    for admin in CustomUser.objects.filter(role__code=RoleCode.ADMIN, is_active=True):
        notify(
            recipient=admin,
            event_type=NotificationType.AI_LISTING_FLAGGED,
            context={
                "product_name": product.name,
                "stall_name": product.farmer.stall_name,
                "check_label": label,
                "summary": review.summary,
                "product_id": product.pk,
            },
        )


def record_admin_decision(product_id: int, decision: str, actor=None) -> None:
    """Pair the admin's approve/reject with the advice they saw, for the agreement figures,
    and close the AI's open flag on the listing: the decision it asked for has been made."""
    review = latest_review(product_id)
    if review is not None and review.admin_decision is None:
        review.admin_decision = decision
        review.admin_decided_at = timezone.now()
        fields = ["admin_decision", "admin_decided_at"]
        if review.auto_action and review.admin_checked_at is None:
            review.admin_checked_at, review.admin_checked_by = review.admin_decided_at, actor
            fields += ["admin_checked_at", "admin_checked_by"]
        review.save(update_fields=fields)
    close_ai_flags(product_id, resolution=f"Listing {decision.lower()} on the approval page.", actor=actor)


def close_ai_flags(product_id: int, *, resolution: str, actor=None) -> int:
    """Close the AI's open flags on a listing once there is nothing left for an admin to decide."""
    return ModerationFlag.objects.filter(
        target_type=FlagTarget.PRODUCT,
        target_id=product_id,
        resolved_at__isnull=True,
        note__startswith=FLAG_NOTE_PREFIX,
    ).update(resolved_at=timezone.now(), resolved_by=actor, resolution=resolution[:500])


def _run_in_background(product_id: int) -> None:
    close_old_connections()
    try:
        review_product(product_id)
    except Exception:
        logger.exception("AI listing review failed for product %s", product_id)
    finally:
        close_old_connections()


def schedule_listing_review(product_id: int) -> None:
    """After the farmer's save commits, review in the background; the sweep catches misses."""
    if settings.AI_MODERATION_RUN_INLINE:
        transaction.on_commit(lambda: review_product(product_id))
    else:
        transaction.on_commit(lambda: _pool.submit(_run_in_background, product_id))


def products_needing_review(limit: int = 50) -> list[int]:
    """PENDING listings whose current content has no usable advice yet (the sweep's work list)."""
    pending = Product.objects.filter(review_status=ReviewStatus.PENDING, is_archived=False).select_related("category")
    due = []
    for product in pending.order_by("created_at")[: limit * 4]:
        previous = latest_review(product.pk)
        listing = listing_from_product(product)
        if previous is None or previous.content_hash != content_hash(listing, AIReviewKind.LISTING):
            due.append(product.pk)
        elif previous.verdict == AIVerdict.UNAVAILABLE and previous.created_at <= timezone.now() - UNAVAILABLE_RETRY_AFTER:
            due.append(product.pk)
        if len(due) >= limit:
            break
    return due
