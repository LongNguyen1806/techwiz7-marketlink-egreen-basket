"""Editing a market reaches the people due there (P2 + P3, reschedule variant).

- name, address, map position: one notice to every shopper with an open order and every stall;
- days or hours: open orders whose pickup no longer fits are kept but marked, and the shopper is
  asked to pick a new time; the admin sees the count and confirms first. One notice per person.
"""

from datetime import time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from markets.conftest import MONDAY, WEDNESDAY
from notifications.models import Notification, NotificationType
from orders.models import OrderStatus, OrderStatusHistory

DETAIL_URL_NAME = "admin-market-detail"
IMPACT_URL_NAME = "admin-market-impact"


def _next(weekday: int):
    today = timezone.localdate()
    return today + timedelta(days=(weekday - today.isoweekday()) % 7 or 7)


def _patch(client, market, body):
    return client.patch(reverse(DETAIL_URL_NAME, args=[market.id]), body, format="json")


@pytest.mark.django_db
class TestPreview:
    def test_counts_the_orders_a_dropped_day_would_move(self, admin_client, market, make_order):
        make_order(pickup_date=_next(WEDNESDAY))
        make_order(pickup_date=_next(MONDAY))

        response = admin_client.post(
            reverse(IMPACT_URL_NAME, args=[market.id]), {"operating_days": [MONDAY]}, format="json"
        )

        assert response.status_code == 200
        data = response.data["data"]
        assert data["orders_to_reschedule"] == 1
        assert data["customers_to_notify"] == 1
        assert data["schedule_changed"] is True
        assert data["location_changed"] is False

    def test_resending_the_same_values_changes_nothing(self, admin_client, market, farmer_market):
        response = admin_client.post(
            reverse(IMPACT_URL_NAME, args=[market.id]),
            {"name": market.name, "address": market.address, "operating_days": [MONDAY, WEDNESDAY],
             "open_time": "06:00", "close_time": "12:00"},
            format="json",
        )

        data = response.data["data"]
        assert data["changed_fields"] == []
        assert data["stalls_to_notify"] == 0

    def test_preview_writes_nothing(self, admin_client, market, make_order):
        order = make_order(pickup_date=_next(WEDNESDAY))

        admin_client.post(
            reverse(IMPACT_URL_NAME, args=[market.id]), {"operating_days": [MONDAY]}, format="json"
        )

        order.refresh_from_db()
        assert order.reschedule_requested_at is None
        assert not Notification.objects.exists()


@pytest.mark.django_db
class TestScheduleChange:
    def test_is_refused_until_confirmed_when_orders_no_longer_fit(
        self, admin_client, market, make_order
    ):
        order = make_order(pickup_date=_next(WEDNESDAY))

        response = _patch(admin_client, market, {"operating_days": [MONDAY]})

        assert response.status_code == 422
        assert response.data["data"]["orders_to_reschedule"] == 1
        order.refresh_from_db()
        market.refresh_from_db()
        assert order.reschedule_requested_at is None
        assert set(market.operating_days.values_list("day_of_week", flat=True)) == {MONDAY, WEDNESDAY}

    def test_confirmed_keeps_the_order_and_asks_for_a_new_time(
        self, admin_client, market, make_order
    ):
        moved = make_order(pickup_date=_next(WEDNESDAY))
        kept = make_order(pickup_date=_next(MONDAY), status=OrderStatus.ACCEPTED)

        response = _patch(
            admin_client, market, {"operating_days": [MONDAY], "confirm_affected_orders": True}
        )

        assert response.status_code == 200
        assert response.data["data"]["orders_to_reschedule"] == 1
        moved.refresh_from_db()
        kept.refresh_from_db()
        assert moved.status == OrderStatus.PLACED
        assert moved.reschedule_requested_at is not None
        assert kept.reschedule_requested_at is None
        assert OrderStatusHistory.objects.filter(
            order=moved, change_reason__contains="new pickup time"
        ).exists()

    def test_an_accepted_order_is_marked_too(self, admin_client, market, make_order):
        order = make_order(pickup_date=_next(MONDAY), status=OrderStatus.ACCEPTED)

        # make_order books 08:00-10:00.
        _patch(admin_client, market,
               {"open_time": "09:00", "close_time": "12:00", "confirm_affected_orders": "true"})

        order.refresh_from_db()
        assert order.status == OrderStatus.ACCEPTED
        assert order.reschedule_requested_at is not None

    def test_each_shopper_gets_one_notice_for_all_their_orders(
        self, admin_client, market, make_order, customer_user
    ):
        make_order(pickup_date=_next(WEDNESDAY))
        make_order(pickup_date=_next(WEDNESDAY) + timedelta(days=7))

        _patch(admin_client, market, {"operating_days": [MONDAY], "confirm_affected_orders": True})

        notices = Notification.objects.filter(recipient=customer_user)
        assert list(notices.values_list("type", flat=True)) == [NotificationType.MARKET_UPDATED]
        message = notices.get().message
        assert "2 of your orders" in message
        assert "choose a new pickup time" in message

    def test_the_stall_hears_about_orders_and_slots_in_one_notice(
        self, admin_client, market, make_slot, make_order, farmer_user
    ):
        make_slot(day_of_week=WEDNESDAY, start=time(7, 0), end=time(9, 0))
        make_order(pickup_date=_next(WEDNESDAY))

        _patch(admin_client, market, {"operating_days": [MONDAY], "confirm_affected_orders": True})

        notice = Notification.objects.get(recipient=farmer_user)
        assert notice.type == NotificationType.MARKET_UPDATED
        assert "1 of your orders" in notice.message
        assert "1 of your pickup slots" in notice.message

    def test_an_order_already_waiting_is_not_told_twice(
        self, admin_client, market, make_order, customer_user
    ):
        make_order(pickup_date=_next(WEDNESDAY))
        _patch(admin_client, market, {"operating_days": [MONDAY], "confirm_affected_orders": True})

        response = _patch(admin_client, market, {"operating_days": [MONDAY, 2]})

        assert response.status_code == 200
        assert Notification.objects.filter(recipient=customer_user).count() == 1

    def test_a_pickup_already_under_way_is_left_alone(self, admin_client, market, make_order):
        order = make_order(pickup_date=timezone.localdate() - timedelta(days=1))

        response = _patch(admin_client, market, {"operating_days": [7]})

        assert response.status_code == 200
        order.refresh_from_db()
        assert order.reschedule_requested_at is None


@pytest.mark.django_db
class TestLocationChange:
    def test_new_address_tells_shoppers_with_open_orders_and_every_stall(
        self, admin_client, market, farmer_market, make_order, customer_user, farmer_user
    ):
        order = make_order(pickup_date=_next(MONDAY))

        response = _patch(admin_client, market, {"address": "5 New Road"})

        assert response.status_code == 200
        order.refresh_from_db()
        assert order.status == OrderStatus.PLACED
        for user in (customer_user, farmer_user):
            notice = Notification.objects.get(recipient=user)
            assert notice.type == NotificationType.MARKET_UPDATED
            assert "5 New Road" in notice.message

    def test_a_new_description_tells_nobody(self, admin_client, market, farmer_market, make_order):
        make_order(pickup_date=_next(MONDAY))

        _patch(admin_client, market, {"description": "Now with a covered car park."})

        assert not Notification.objects.exists()
