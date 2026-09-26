"""Delete sign-ups that were never used, to stop them accumulating.

Default is a dry run: the command prints what it would delete and changes nothing. Deleting
an account cascades to its profile and cannot be undone, so removal needs --apply said out
loud rather than being the default.
"""

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.utils import timezone

from accounts.models import FarmerStatus
from marketlink_core.policies.roles import RoleCode
from orders.models import Order
from system.models import AuditAction
from system.services import log_security_event

DEFAULT_MONTHS = 3
User = get_user_model()


def stale_accounts(*, months: int = DEFAULT_MONTHS):
    """Accounts with no sign-in for `months` and no order ever placed or received.

    Kept deliberately narrow: shoppers, and stalls that were never approved. An approved
    stall is left alone even with no orders yet - it may have listed produce and be waiting
    for its first customer. Admins are never touched.
    """
    cutoff = timezone.now() - timedelta(days=months * 30)

    placed = Order.objects.filter(customer_id=OuterRef("pk"))
    received = Order.objects.filter(farmer_id=OuterRef("pk"))

    return (
        User.objects.filter(
            # Never signed in and created long ago, or signed in once and not since.
            Q(last_login__isnull=True, date_joined__lt=cutoff) | Q(last_login__lt=cutoff)
        )
        .filter(
            Q(role__code=RoleCode.CUSTOMER)
            | Q(
                role__code=RoleCode.FARMER,
                farmer_profile__status__in=[FarmerStatus.PENDING, FarmerStatus.REJECTED],
            )
        )
        .exclude(is_superuser=True)
        .exclude(is_staff=True)
        .annotate(has_placed=Exists(placed), has_received=Exists(received))
        .filter(has_placed=False, has_received=False)
        .select_related("role")
        .order_by("id")
    )


class Command(BaseCommand):
    help = "List (or with --apply, delete) accounts that were never used."

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually delete. Without this the command only reports.",
        )
        parser.add_argument(
            "--months",
            type=int,
            default=DEFAULT_MONTHS,
            help=f"How long an account must have been idle (default {DEFAULT_MONTHS}).",
        )

    def handle(self, *args, **options):
        months = options["months"]
        if months < 1:
            self.stderr.write("--months must be at least 1.")
            return

        # Listed before deleting: once the rows are gone the emails are gone with them.
        rows = [
            {"id": user.pk, "email": user.email, "role": user.role.code if user.role_id else None}
            for user in stale_accounts(months=months)
        ]

        if not rows:
            self.stdout.write(f"No accounts idle for {months} months without orders.")
            return

        for row in rows:
            self.stdout.write(f"  {row['id']:>5}  {row['role'] or '-':<9}  {row['email']}")

        if not options["apply"]:
            self.stdout.write(
                self.style.WARNING(
                    f"{len(rows)} account(s) would be deleted. Re-run with --apply to do it."
                )
            )
            return

        with transaction.atomic():
            User.objects.filter(pk__in=[row["id"] for row in rows]).delete()
            # No request behind a cron run, so this goes in without IP or endpoint.
            log_security_event(
                action=AuditAction.ACCOUNT_PURGED,
                user=None,
                endpoint=None,
                method=None,
                ip_address=None,
                user_agent=None,
                status_code=None,
                request_id=None,
                details={"months": months, "count": len(rows), "accounts": rows},
            )

        self.stdout.write(self.style.SUCCESS(f"Deleted {len(rows)} account(s)."))
