import time
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from catalog.ai_review import gemini
from catalog.ai_review.service import latest_review, review_product
from catalog.models import AIReviewKind, Product, ReviewStatus


class Command(BaseCommand):
    help = (
        "Weekly AI check of the photos of listings on sale. Only raises flags and tells admins; "
        "it never hides a listing. Schedule once a week (cron / the host's scheduler)."
    )

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=200, help="Most photos per run (default 200).")
        parser.add_argument(
            "--max-age-days", type=int, default=7,
            help="Re-check a photo whose last check is older than this (default 7: every photo weekly).",
        )

    def handle(self, *args, **options):
        if not gemini.is_configured():
            self.stdout.write(self.style.WARNING("AI review is off or GEMINI_API_KEY is empty; nothing checked."))
            return
        cutoff = timezone.now() - timedelta(days=options["max_age_days"])
        on_sale = (
            Product.objects.filter(review_status=ReviewStatus.APPROVED, is_archived=False, is_hidden_by_admin=False)
            .exclude(image="")
            .exclude(image__isnull=True)
            .order_by("id")
        )
        pause = settings.AI_MODERATION_BATCH_PAUSE_MS / 1000
        checked, flagged, skipped = 0, 0, 0
        for product in on_sale.iterator():
            if checked >= options["limit"]:
                break
            previous = latest_review(product.pk, AIReviewKind.WEEKLY_IMAGE)
            stale = previous is None or previous.created_at < cutoff
            review = review_product(product.pk, kind=AIReviewKind.WEEKLY_IMAGE, force=stale)
            if review is None or (previous is not None and review.pk == previous.pk):
                skipped += 1
                continue
            checked += 1
            flagged += review.verdict != "PASS"
            if pause:
                time.sleep(pause)
        self.stdout.write(self.style.SUCCESS(f"Checked {checked} photo(s), {flagged} need an admin, {skipped} unchanged and recent."))
