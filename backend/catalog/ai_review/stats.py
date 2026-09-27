"""How the AI's advice compared with what admins decided: the numbers that say whether to trust it."""

from datetime import timedelta

from django.db.models import Count, Max
from django.utils import timezone

from catalog.ai_review.service import FLAG_NOTE_PREFIX
from catalog.models import AIReviewKind, AIVerdict, ProductAIReview, ReviewStatus
from system.models import FlagTarget, ModerationFlag


def ai_review_stats(*, days: int = 30) -> dict:
    days = max(1, min(days, 365))
    since = timezone.now() - timedelta(days=days)
    listing = ProductAIReview.objects.filter(kind=AIReviewKind.LISTING, created_at__gte=since)

    by_verdict = {verdict: 0 for verdict in AIVerdict.values}
    for row in listing.values("verdict").annotate(total=Count("id")):
        by_verdict[row["verdict"]] = row["total"]

    decided = listing.exclude(admin_decision__isnull=True)

    def count(verdict: str, decision: str) -> int:
        return decided.filter(verdict=verdict, admin_decision=decision).count()

    passed_approved = count(AIVerdict.PASS, ReviewStatus.APPROVED)
    passed_rejected = count(AIVerdict.PASS, ReviewStatus.REJECTED)
    flagged_rejected = count(AIVerdict.LIKELY_VIOLATION, ReviewStatus.REJECTED)
    flagged_approved = count(AIVerdict.LIKELY_VIOLATION, ReviewStatus.APPROVED)
    clear_cut = passed_approved + passed_rejected + flagged_rejected + flagged_approved

    return {
        "period_days": days,
        "reviewed": sum(by_verdict.values()),
        "by_verdict": by_verdict,
        "decided": decided.count(),
        # Only the clear-cut calls count: PASS vs LIKELY_VIOLATION. NEEDS_REVIEW asks for a look
        # and is right either way.
        "agreement_rate": round((passed_approved + flagged_rejected) / clear_cut, 3) if clear_cut else None,
        "passed_then_approved": passed_approved,
        "missed": passed_rejected,  # AI said fine, admin refused
        "caught": flagged_rejected,  # AI flagged, admin refused
        "false_alarms": flagged_approved,  # AI flagged, admin approved
        "review_then_approved": count(AIVerdict.NEEDS_REVIEW, ReviewStatus.APPROVED),
        "review_then_rejected": count(AIVerdict.NEEDS_REVIEW, ReviewStatus.REJECTED),
        "ai_unavailable": by_verdict[AIVerdict.UNAVAILABLE],
        "open_ai_flags": ModerationFlag.objects.filter(
            target_type=FlagTarget.PRODUCT, resolved_at__isnull=True, note__startswith=FLAG_NOTE_PREFIX
        ).count(),
        "last_photo_check_at": ProductAIReview.objects.filter(kind=AIReviewKind.WEEKLY_IMAGE).aggregate(last=Max("created_at"))["last"],
    }
