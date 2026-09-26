"""Lỗi A: closing a market (AD-17) must not tell anyone the farmer was suspended.

Service-level tests: they call the services directly, so they need no URL routing.
"""

from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.services.farmer_status_service import suspend_farmer
from markets.services.market_service import deactivate_market
from notifications.models import Notification, NotificationType
from orders.customer.serializers_customer import SYSTEM_REASON_TEXT as CUSTOMER_REASON_TEXT
from orders.models import ActorRole, ChangeReason, OrderStatus, OrderStatusHistory
from orders.services.fsm import SYSTEM_REASON_TEXT, transition_order

REASON = "The market building is being demolished."


def _decline_row(order):
    return OrderStatusHistory.objects.get(order=order, to_status=OrderStatus.DECLINED)


@pytest.mark.django_db
class TestClosingAMarket:
    def test_order_history_says_the_market_closed(self, market, make_order, admin_user):
        order = make_order(pickup_date=timezone.localdate() + timedelta(days=1))

        deactivate_market(market_id=market.id, reason=REASON, actor=admin_user)

        row = _decline_row(order)
        assert row.change_reason == ChangeReason.MARKET_CLOSED_BY_ADMIN
        assert row.actor_role == ActorRole.ADMIN

    def test_customer_gets_one_market_closed_notice_and_no_declined_notice(
        self, market, make_order, admin_user, customer_user
    ):
        make_order(pickup_date=timezone.localdate() + timedelta(days=1))
        make_order(pickup_date=timezone.localdate() + timedelta(days=2))

        deactivate_market(market_id=market.id, reason=REASON, actor=admin_user)

        notices = Notification.objects.filter(recipient=customer_user)
        assert list(notices.values_list("type", flat=True)) == [NotificationType.MARKET_CLOSED]
        assert "suspended" not in notices.get().message

    def test_nothing_mentions_a_suspension(self, market, make_order, admin_user):
        make_order(pickup_date=timezone.localdate() + timedelta(days=1))

        deactivate_market(market_id=market.id, reason=REASON, actor=admin_user)

        assert not Notification.objects.filter(message__icontains="suspended").exists()

    def test_both_sides_have_a_readable_reason(self):
        assert SYSTEM_REASON_TEXT[ChangeReason.MARKET_CLOSED_BY_ADMIN] == (
            "The market has been closed by an administrator."
        )
        assert "market has closed" in CUSTOMER_REASON_TEXT[ChangeReason.MARKET_CLOSED_BY_ADMIN]


@pytest.mark.django_db
class TestSuspensionIsUnchanged:
    def test_suspending_a_farmer_still_stamps_the_suspension(
        self, market, make_order, admin_user, approved_farmer, customer_user
    ):
        order = make_order(pickup_date=timezone.localdate() + timedelta(days=1))

        suspend_farmer(farmer_id=approved_farmer.pk, reason="Selling spoiled goods", actor=admin_user)

        assert _decline_row(order).change_reason == ChangeReason.FARMER_SUSPENDED_BY_ADMIN
        declined = Notification.objects.get(recipient=customer_user, type=NotificationType.ORDER_DECLINED)
        assert "suspended" in declined.message


@pytest.mark.django_db
class TestAdminOnlyOptions:
    def test_farmer_cannot_pass_an_admin_reason(self, make_order, approved_farmer):
        order = make_order(pickup_date=timezone.localdate() + timedelta(days=1))

        with pytest.raises(ValueError):
            transition_order(
                order_id=order.id, to_status=OrderStatus.DECLINED, actor=approved_farmer.user,
                actor_role=ActorRole.FARMER, expected_version=order.version, reason="No stock left",
                admin_reason=ChangeReason.MARKET_CLOSED_BY_ADMIN,
            )

    def test_customer_cannot_silence_notifications(self, make_order, customer_user):
        order = make_order(pickup_date=timezone.localdate() + timedelta(days=1))

        with pytest.raises(ValueError):
            transition_order(
                order_id=order.id, to_status=OrderStatus.CANCELLED, actor=customer_user,
                actor_role=ActorRole.CUSTOMER, expected_version=order.version, notify_customer=False,
            )

    def test_a_reason_that_does_not_fit_the_edge_is_refused(self, make_order, admin_user):
        order = make_order(pickup_date=timezone.localdate() + timedelta(days=1))

        # Market closure declines orders; it can never be stamped on a cancellation (T5).
        with pytest.raises(ValueError):
            transition_order(
                order_id=order.id, to_status=OrderStatus.CANCELLED, actor=admin_user,
                actor_role=ActorRole.ADMIN, admin_reason=ChangeReason.MARKET_CLOSED_BY_ADMIN,
            )

        order.refresh_from_db()
        assert order.status == OrderStatus.PLACED
