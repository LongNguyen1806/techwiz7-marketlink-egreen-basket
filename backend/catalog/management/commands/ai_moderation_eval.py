import time
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand

from catalog.ai_review import gemini
from catalog.ai_review.eval_cases import EVAL_CASES
from catalog.ai_review.service import evaluate
from catalog.ai_review.types import ListingInput
from catalog.models import AIVerdict, Category


def _outcome(verdict: str) -> str:
    return "PASS" if verdict in (AIVerdict.PASS, AIVerdict.UNAVAILABLE) else "FLAG"


class Command(BaseCommand):
    help = (
        "Measure the listing review on a fixed set of listings with known answers. Prints the rule "
        "layer alone and rules + AI (when a GEMINI_API_KEY is set). Saves nothing."
    )

    def add_arguments(self, parser):
        parser.add_argument("--rules-only", action="store_true", help="Skip the model even if a key is set.")

    def handle(self, *args, **options):
        use_ai = gemini.is_configured() and not options["rules_only"]
        categories = {category.name: category for category in Category.objects.all()}
        pause = settings.AI_MODERATION_BATCH_PAUSE_MS / 1000

        rows, rules_ok, full_ok, answered, answered_ok = [], 0, 0, 0, 0
        for index, case in enumerate(EVAL_CASES):
            category = categories.get(case["category"])
            listing = ListingInput(
                name=case["name"],
                description=case["description"],
                category_id=category.pk if category else None,
                category_name=case["category"],
                unit=case["unit"],
                price=Decimal(case["price"]),
                stock_quantity=case["stock"],
            )
            rules_only = evaluate(listing, use_ai=False)
            rules_hit = _outcome(rules_only["verdict"]) == case["expect"]
            rules_ok += rules_hit
            full = evaluate(listing, use_ai=True) if use_ai else rules_only
            full_hit = _outcome(full["verdict"]) == case["expect"]
            full_ok += full_hit
            if use_ai and full["ai_used"]:
                answered += 1
                answered_ok += full_hit
            rows.append((case, rules_only, rules_hit, full, full_hit))
            if use_ai and pause and index < len(EVAL_CASES) - 1:
                time.sleep(pause)

        width = max(len(case["label"]) for case in EVAL_CASES)
        self.stdout.write(f"{'Case'.ljust(width)}  Expect  Layer  Rules            {'Rules+AI' if use_ai else ''}")
        for case, rules_only, rules_hit, full, full_hit in rows:
            mark = lambda hit: "ok " if hit else "MISS"  # noqa: E731
            line = f"{case['label'].ljust(width)}  {case['expect']:<6}  {case['layer']:<5}  {mark(rules_hit)} {rules_only['verdict']:<16}"
            if use_ai:
                line += f"  {mark(full_hit)} {full['verdict']}"
                if full["ai_error"]:
                    line += f"  ({full['ai_error']})"
            self.stdout.write(line)

        total = len(EVAL_CASES)
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Rules only: {rules_ok}/{total} correct ({rules_ok / total:.0%})."))
        rules_cases = [row for row in rows if row[0]["layer"] in ("rules", "-")]
        caught = sum(1 for row in rules_cases if row[2])
        self.stdout.write(f"  on cases the rules are meant to handle: {caught}/{len(rules_cases)}")
        if use_ai:
            self.stdout.write(self.style.SUCCESS(f"Rules + AI: {full_ok}/{total} correct ({full_ok / total:.0%})."))
            if answered:
                self.stdout.write(f"  cases the AI actually answered: {answered}/{total}, of which {answered_ok} correct ({answered_ok / answered:.0%})")
            ai_cases = [row for row in rows if row[0]["layer"] == "ai"]
            ai_measured = [row for row in ai_cases if row[3]["ai_used"]]
            self.stdout.write(
                f"  meaning-only cases (only the AI can catch): {sum(1 for row in ai_measured if row[4])}/{len(ai_measured)} caught"
                f" ({len(ai_cases) - len(ai_measured)} not measured: AI unavailable or skipped)"
            )
        else:
            self.stdout.write(self.style.WARNING("AI layer not run (AI_MODERATION_ENABLED off, no GEMINI_API_KEY, or --rules-only)."))
