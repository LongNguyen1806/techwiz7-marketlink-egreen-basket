from datetime import timedelta
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone

from accounts.models import FarmerStatus
from system.models import AuditAction, AuditLog

User = get_user_model()


def _age(user, *, days: int) -> None:
    stale = timezone.now() - timedelta(days=days)
    User.objects.filter(pk=user.pk).update(date_joined=stale, last_login=None)


def _run(*args) -> str:
    out = StringIO()
    call_command("purge_stale_accounts", *args, stdout=out, stderr=out)
    return out.getvalue()


@pytest.mark.django_db
def test_a_dry_run_reports_without_deleting(customer_user):
    _age(customer_user, days=200)

    output = _run()

    assert customer_user.email in output
    assert "would be deleted" in output
    # The whole point of the default: nothing is gone yet.
    assert User.objects.filter(pk=customer_user.pk).exists()


@pytest.mark.django_db
def test_apply_deletes_and_audits(customer_user):
    _age(customer_user, days=200)

    _run("--apply")

    assert not User.objects.filter(pk=customer_user.pk).exists()
    entry = AuditLog.objects.get(action=AuditAction.ACCOUNT_PURGED)
    # The emails are recorded before deletion; afterwards there is nothing left to name.
    assert entry.details["accounts"][0]["email"] == customer_user.email
    assert entry.details["count"] == 1


@pytest.mark.django_db
def test_an_account_with_any_order_is_kept(customer_user, make_order):
    _age(customer_user, days=400)
    make_order(pickup_date=timezone.localdate() - timedelta(days=300))

    _run("--apply")

    assert User.objects.filter(pk=customer_user.pk).exists()


@pytest.mark.django_db
def test_a_recent_account_is_kept(customer_user):
    _run("--apply")

    assert User.objects.filter(pk=customer_user.pk).exists()


@pytest.mark.django_db
def test_an_approved_stall_is_never_purged(farmer_user):
    profile = farmer_user.farmer_profile
    profile.status = FarmerStatus.APPROVED
    profile.save(update_fields=["status"])
    _age(farmer_user, days=400)

    _run("--apply")

    # It may have produce listed and simply be waiting for a first customer.
    assert User.objects.filter(pk=farmer_user.pk).exists()


@pytest.mark.django_db
def test_a_stall_that_was_never_approved_is_purged(farmer_user):
    _age(farmer_user, days=400)

    _run("--apply")

    assert not User.objects.filter(pk=farmer_user.pk).exists()


@pytest.mark.django_db
def test_an_admin_is_never_purged(admin_user):
    _age(admin_user, days=400)

    _run("--apply")

    assert User.objects.filter(pk=admin_user.pk).exists()


@pytest.mark.django_db
def test_months_must_be_positive(customer_user):
    _age(customer_user, days=400)

    output = _run("--months", "0", "--apply")

    assert "at least 1" in output
    assert User.objects.filter(pk=customer_user.pk).exists()
