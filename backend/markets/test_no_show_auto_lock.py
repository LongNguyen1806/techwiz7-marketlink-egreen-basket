"""Three missed pickups in the at-risk window lock the shopper's account automatically.

Kept with the market fixtures, which build real orders at a real stall.
"""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.services.customer_status_service import activate_customer
from notifications.models import Notification, NotificationType
from orders.models import ActorRole, OrderStatus
from orders.services.fsm import transition_order
from system.models import AuditAction, AuditLog


def _no_show(order, farmer, capture):
    with capture(execute=True):
        transition_order(
            order_id=order.pk,
            to_status=OrderStatus.NO_SHOW,
            actor=farmer.user,
            actor_role=ActorRole.FARMER,
            expected_version=order.version,
        )


@pytest.fixture
def missed(make_order):
    """An order whose pickup window has ended, ready to be marked a no-show."""

    def _make(days_ago=1):
        return make_order(
            pickup_date=timezone.localdate() - timedelta(days=days_ago),
            status=OrderStatus.READY_FOR_PICKUP,
        )

    return _make


@pytest.mark.django_db
class TestAutoLock:
    def test_two_no_shows_do_not_lock(
        self, missed, approved_farmer, customer_user, django_capture_on_commit_callbacks
    ):
        for _ in range(2):
            _no_show(missed(), approved_farmer, django_capture_on_commit_callbacks)

        customer_user.refresh_from_db()
        assert customer_user.is_active is True

    def test_the_third_no_show_locks_and_records_why(
        self, missed, make_order, approved_farmer, customer_user, django_capture_on_commit_callbacks
    ):
        orders = [missed(days_ago=d) for d in (3, 2, 1)]
        still_open = make_order(pickup_date=timezone.localdate() + timedelta(days=2))

        for order in orders:
            _no_show(order, approved_farmer, django_capture_on_commit_callbacks)

        customer_user.refresh_from_db()
        assert customer_user.is_active is False
        reason = customer_user.customer_profile.deactivation_reason
        assert reason.startswith("Auto-locked")
        for order in orders:
            assert f"#{order.pk}" in reason

        log = AuditLog.objects.get(action=AuditAction.CUSTOMER_AUTO_LOCKED)
        assert log.user is None
        assert log.details["customer_id"] == customer_user.pk
        assert log.details["no_show_order_ids"] == [order.pk for order in orders]
        assert log.details["cancelled_open_orders"] == 1

        still_open.refresh_from_db()
        assert still_open.status == OrderStatus.CANCELLED
        assert Notification.objects.filter(
            recipient=customer_user, type=NotificationType.ACCOUNT_LOCKED_NO_SHOW
        ).exists()

    def test_old_no_shows_outside_the_window_do_not_count(
        self, missed, approved_farmer, customer_user, django_capture_on_commit_callbacks
    ):
        old = [missed(days_ago=40), missed(days_ago=39)]
        for order in old:
            _no_show(order, approved_farmer, django_capture_on_commit_callbacks)
        from orders.models import OrderStatusHistory

        OrderStatusHistory.objects.filter(order__in=old).update(
            created_at=timezone.now() - timedelta(days=40)
        )

        _no_show(missed(), approved_farmer, django_capture_on_commit_callbacks)

        customer_user.refresh_from_db()
        assert customer_user.is_active is True

    def test_unlocking_gives_a_fresh_start(
        self, missed, approved_farmer, customer_user, admin_user,
        django_capture_on_commit_callbacks,
    ):
        for _ in range(3):
            _no_show(missed(), approved_farmer, django_capture_on_commit_callbacks)
        activate_customer(customer_id=customer_user.pk)
        AuditLog.objects.create(
            action=AuditAction.CUSTOMER_ACTIVATED, user=admin_user,
            details={"customer_id": customer_user.pk},
        )

        _no_show(missed(), approved_farmer, django_capture_on_commit_callbacks)

        customer_user.refresh_from_db()
        assert customer_user.is_active is True


@pytest.mark.django_db
class TestTheAdminSeesTheOrders:
    def test_customer_detail_lists_the_three_missed_orders(
        self, admin_client, missed, approved_farmer, customer_user,
        django_capture_on_commit_callbacks,
    ):
        orders = [missed(days_ago=d) for d in (3, 2, 1)]
        for order in orders:
            _no_show(order, approved_farmer, django_capture_on_commit_callbacks)

        response = admin_client.get(reverse("admin-customer-detail", args=[customer_user.pk]))

        assert response.status_code == 200
        lock = response.data["data"]["auto_lock"]
        assert [row["id"] for row in lock["orders"]] == [order.pk for order in orders]
        assert lock["orders"][0]["stall_name"] == approved_farmer.stall_name

    def test_an_active_account_has_no_auto_lock(self, admin_client, customer_user):
        response = admin_client.get(reverse("admin-customer-detail", args=[customer_user.pk]))

        assert response.data["data"]["auto_lock"] is None
