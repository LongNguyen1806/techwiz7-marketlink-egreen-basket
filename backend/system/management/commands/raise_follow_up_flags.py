from django.core.management.base import BaseCommand

from system.auto_flags import scan_existing


class Command(BaseCommand):
    help = (
        "Put what is already in the database through the automatic follow-up rules: products "
        "with repeated low ratings, and shoppers past the no-show limit. Review text is checked by "
        "the AI as each review is written. Safe to run again: nothing already in the queue is "
        "added twice."
    )

    def handle(self, *args, **options):
        raised = scan_existing()
        self.stdout.write(
            self.style.SUCCESS(
                "Follow-up queue: "
                f"{raised['products']} product(s), {raised['customers']} shopper(s) flagged."
            )
        )
