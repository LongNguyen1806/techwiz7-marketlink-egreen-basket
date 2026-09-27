import time

from django.conf import settings
from django.core.management.base import BaseCommand

from catalog.ai_review.service import products_needing_review, review_product


class Command(BaseCommand):
    help = (
        "AI review of listings waiting for approval that have no advice for their current content "
        "(the background review failed, the server restarted, or the AI was unavailable). "
        "Schedule every 10 minutes, like expire_orders."
    )

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=30, help="Most listings per run (default 30).")

    def handle(self, *args, **options):
        ids = products_needing_review(limit=options["limit"])
        pause = settings.AI_MODERATION_BATCH_PAUSE_MS / 1000
        verdicts: dict[str, int] = {}
        for index, product_id in enumerate(ids):
            review = review_product(product_id)
            if review is not None:
                verdicts[review.verdict] = verdicts.get(review.verdict, 0) + 1
            if index < len(ids) - 1 and pause:
                time.sleep(pause)
        summary = ", ".join(f"{name} {total}" for name, total in sorted(verdicts.items())) or "nothing to do"
        self.stdout.write(self.style.SUCCESS(f"Reviewed {len(ids)} listing(s): {summary}."))
