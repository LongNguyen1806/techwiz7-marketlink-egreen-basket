"""The shopper's side of a market schedule change: pick a new pickup time, or cancel.

Q1: a placed order takes the new time straight away; an accepted one sends it to the stall
    as a change request, and stays marked until the stall approves.
Q2: left alone, the order is declined when its old pickup time comes.
Q3: the old cutoff does not lock the shopper out, but the new time must pass every rule:
    not in the past, before the stall's cutoff, a market day, inside the market's hours.
"""

from datetime import datetime, time, timedelta

import pytest
from django.utils import timezone

from marketlink_core.exceptions import BusinessValidationError, UnprocessableEntityError
from markets.conftest import MONDAY, WEDNESDAY
from notifications.models import Notification, NotificationType
from orders.models import ActorRole, ChangeReason, OrderStatus, OrderStatusHistory
from orders.services.expiry import expire_overdue_orders
from orders.services.farmer_change_request import (
    approve_change_request,
    reject_change_request,
)
from orders.services.fsm import transition_order
from orders.services.modify import modify_order


def _next(weekday: int):
    today = timezone.localdate()
    return today + timedelta(days=(weekday - today.isoweekday()) % 7 or 7)


@pytest.fixture
def open_farmer(approved_farmer):
    approved_farmer.operating_days = [1, 2, 3, 4, 5, 6, 7]
    approved_farmer.save(update_fields=["operating_days"])
    return approved_farmer


@pytest.fixture
def monday_slot(make_slot, open_farmer):
    return make_slot(day_of_week=MONDAY, start=time(7, 0), end=time(9, 0))


def _flag(order, *, past_cutoff=False):
    order.reschedule_requested_at = timezone.now()
    if past_cutoff:
        order.cutoff_at = timezone.now() - timedelta(hours=1)
    order.save(update_fields=["reschedule_requested_at", "cutoff_at"])
    return order


def _reschedule(order, slot, pickup_date, **extra):
    return modify_order(
        order_id=order.pk,
        actor=order.customer,
        expected_version=order.version,
        pickup_date=pickup_date,
        pickup_slot_id=slot.pk,
        **extra,
    )


def _item(order):
    from catalog.models import Category, Product, Unit
    from orders.models import OrderItem

    category = Category.objects.create(name="Greens", icon="carrot", display_order=1)
    product = Product.objects.create(
        farmer=order.farmer, category=category, name="Kale", price="2.00", unit=Unit.KG,
        stock_quantity=10,
    )
    return OrderItem.objects.create(
        order=order, product=product, product_name="Kale", unit=Unit.KG, unit_price="2.00",
        quantity=2, line_total="4.00",
    )


@pytest.mark.django_db
class TestPickingANewTime:
    def test_works_past_the_old_cutoff_and_clears_the_mark(self, make_order, monday_slot):
        order = _flag(make_order(pickup_date=_next(WEDNESDAY)), past_cutoff=True)

        _reschedule(order, monday_slot, _next(MONDAY))

        order.refresh_from_db()
        assert order.reschedule_requested_at is None
        assert order.pickup_date == _next(MONDAY)
        assert order.pickup_slot_id == monday_slot.pk
        assert timezone.localtime(order.pickup_start_at).time() == time(7, 0)

    def test_an_accepted_order_asks_the_stall_first(self, make_order, monday_slot):
        old_day = _next(WEDNESDAY)
        order = _flag(make_order(pickup_date=old_day, status=OrderStatus.ACCEPTED),
                      past_cutoff=True)

        _reschedule(order, monday_slot, _next(MONDAY))

        order.refresh_from_db()
        assert order.pickup_date == old_day
        assert order.pending_change["pickup_slot_id"] == monday_slot.pk
        assert order.pending_change["pickup_date"] == _next(MONDAY).isoformat()
        assert order.reschedule_requested_at is not None

    def test_the_stall_approving_moves_it_and_clears_the_mark(
        self, make_order, monday_slot, approved_farmer, customer_user
    ):
        order = _flag(make_order(pickup_date=_next(WEDNESDAY), status=OrderStatus.ACCEPTED))
        _reschedule(order, monday_slot, _next(MONDAY))
        order.refresh_from_db()

        approve_change_request(order_id=order.pk, farmer_id=approved_farmer.pk,
                               expected_version=order.version, actor=approved_farmer.user)

        order.refresh_from_db()
        assert order.pickup_date == _next(MONDAY)
        assert order.pending_change is None
        assert order.reschedule_requested_at is None
        assert Notification.objects.filter(
            recipient=customer_user, type=NotificationType.ORDER_CHANGE_APPROVED
        ).exists()

    def test_the_stall_refusing_lets_the_shopper_pick_again(
        self, make_order, monday_slot, make_slot, approved_farmer
    ):
        order = _flag(make_order(pickup_date=_next(WEDNESDAY), status=OrderStatus.ACCEPTED))
        _reschedule(order, monday_slot, _next(MONDAY))
        order.refresh_from_db()

        reject_change_request(order_id=order.pk, farmer_id=approved_farmer.pk,
                              expected_version=order.version, actor=approved_farmer.user,
                              reason="Too early for us")

        order.refresh_from_db()
        assert order.pending_change is None
        assert order.reschedule_requested_at is not None
        later = make_slot(day_of_week=MONDAY, start=time(10, 0), end=time(11, 0))
        _reschedule(order, later, _next(MONDAY))
        order.refresh_from_db()
        assert order.pending_change["pickup_slot_id"] == later.pk

    def test_the_stall_is_told_the_new_time(self, make_order, monday_slot, farmer_user):
        order = _flag(make_order(pickup_date=_next(WEDNESDAY)))

        _reschedule(order, monday_slot, _next(MONDAY))

        assert Notification.objects.filter(
            recipient=farmer_user, type=NotificationType.ORDER_MODIFIED
        ).exists()

    def test_only_the_time_may_change(self, make_order, monday_slot):
        order = _flag(make_order(pickup_date=_next(WEDNESDAY)))
        item = _item(order)

        with pytest.raises(BusinessValidationError):
            _reschedule(order, monday_slot, _next(MONDAY),
                        items_data=[{"product_id": item.product_id, "quantity": 5}])

    def test_sending_the_same_items_back_is_fine(self, make_order, monday_slot):
        order = _flag(make_order(pickup_date=_next(WEDNESDAY)))
        item = _item(order)

        _reschedule(order, monday_slot, _next(MONDAY),
                    items_data=[{"product_id": item.product_id, "quantity": 2}])

        order.refresh_from_db()
        assert order.reschedule_requested_at is None

    def test_a_new_time_is_required(self, make_order):
        order = _flag(make_order(pickup_date=_next(WEDNESDAY)))

        with pytest.raises(BusinessValidationError):
            modify_order(order_id=order.pk, actor=order.customer,
                         expected_version=order.version, note="hello")


@pytest.mark.django_db
class TestTheNewTimeFollowsTheRules:
    def test_a_time_past_the_stall_cutoff_is_refused(self, make_order, make_slot, open_farmer, market):
        soon = timezone.localtime() + timedelta(hours=2)
        market.operating_days.get_or_create(day_of_week=soon.isoweekday())
        market.open_time, market.close_time = time(0, 0), time(23, 59)
        market.save(update_fields=["open_time", "close_time"])
        start = soon.replace(minute=0, second=0, microsecond=0).time()
        end = (datetime.combine(soon.date(), start) + timedelta(minutes=30)).time()
        if end <= start:
            pytest.skip("too close to midnight to build a slot")
        slot = make_slot(day_of_week=soon.isoweekday(), start=start, end=end)
        order = _flag(make_order(pickup_date=_next(WEDNESDAY)))

        with pytest.raises(UnprocessableEntityError) as exc:
            _reschedule(order, slot, soon.date())
        assert exc.value.code == "CUTOFF_PASSED"

    def test_a_day_the_market_does_not_open_is_refused(self, make_order, make_slot, open_farmer):
        saturday_slot = make_slot(day_of_week=6, start=time(7, 0), end=time(9, 0))
        order = _flag(make_order(pickup_date=_next(WEDNESDAY)))

        with pytest.raises(UnprocessableEntityError):
            _reschedule(order, saturday_slot, _next(6))

    def test_a_slot_outside_the_market_hours_is_refused(self, make_order, make_slot, open_farmer):
        late = make_slot(day_of_week=MONDAY, start=time(13, 0), end=time(14, 0))
        order = _flag(make_order(pickup_date=_next(WEDNESDAY)))

        with pytest.raises(UnprocessableEntityError) as exc:
            _reschedule(order, late, _next(MONDAY))
        assert "opening hours" in str(exc.value.detail)

    def test_a_date_in_the_past_is_refused(self, make_order, monday_slot):
        order = _flag(make_order(pickup_date=_next(WEDNESDAY)))

        with pytest.raises(UnprocessableEntityError):
            _reschedule(order, monday_slot, _next(MONDAY) - timedelta(days=7 * 3))


@pytest.mark.django_db
class TestCancellingOrLettingItLapse:
    def test_the_shopper_can_cancel_past_the_old_cutoff(self, make_order):
        order = _flag(make_order(pickup_date=_next(WEDNESDAY)), past_cutoff=True)

        transition_order(order_id=order.pk, to_status=OrderStatus.CANCELLED,
                         actor=order.customer, actor_role=ActorRole.CUSTOMER,
                         expected_version=order.version)

        order.refresh_from_db()
        assert order.status == OrderStatus.CANCELLED

    def test_left_alone_it_is_declined_at_the_old_pickup_time(
        self, make_order, customer_user, farmer_user
    ):
        order = make_order(pickup_date=timezone.localdate() - timedelta(days=1),
                           status=OrderStatus.ACCEPTED)
        _flag(order)

        expire_overdue_orders()

        order.refresh_from_db()
        assert order.status == OrderStatus.DECLINED
        row = OrderStatusHistory.objects.get(order=order, to_status=OrderStatus.DECLINED)
        assert row.change_reason == ChangeReason.MARKET_SCHEDULE_CHANGED_BY_ADMIN
        for user in (customer_user, farmer_user):
            notice = Notification.objects.get(recipient=user)
            assert notice.type == NotificationType.ORDER_RESCHEDULE_MISSED
            assert "no new pickup time was chosen" in notice.message
        assert "back in your stock" in Notification.objects.get(recipient=farmer_user).message

    def test_a_request_the_stall_never_answered_says_so(
        self, make_order, monday_slot, customer_user
    ):
        order = _flag(make_order(pickup_date=timezone.localdate() - timedelta(days=1),
                                 status=OrderStatus.ACCEPTED))
        order.pending_change = {"items": None, "pickup_date": _next(MONDAY).isoformat(),
                                "pickup_slot_id": monday_slot.pk, "note": None,
                                "requested_at": timezone.now().isoformat()}
        order.save(update_fields=["pending_change"])

        expire_overdue_orders()

        order.refresh_from_db()
        assert order.status == OrderStatus.DECLINED
        notice = Notification.objects.get(recipient=customer_user)
        assert "the stall did not confirm the new pickup time" in notice.message

    def test_a_placed_one_is_declined_not_expired(self, make_order):
        order = _flag(make_order(pickup_date=timezone.localdate() - timedelta(days=1)))

        expire_overdue_orders()

        order.refresh_from_db()
        assert order.status == OrderStatus.DECLINED

    def test_an_order_still_ahead_is_not_touched(self, make_order):
        order = _flag(make_order(pickup_date=_next(WEDNESDAY)))

        expire_overdue_orders()

        order.refresh_from_db()
        assert order.status == OrderStatus.PLACED


@pytest.mark.django_db
class TestThroughTheCustomerApi:
    """What Long's EditOrderPage sees and sends, once the branches are merged."""

    @pytest.fixture
    def customer_client(self, api_client, customer_user):
        api_client.force_authenticate(user=customer_user)
        return api_client

    def test_an_accepted_order_offers_a_change_request(self, customer_client, make_order):
        order = _flag(make_order(pickup_date=_next(WEDNESDAY), status=OrderStatus.ACCEPTED),
                      past_cutoff=True)

        response = customer_client.get(f"/api/customer/orders/{order.pk}/")

        assert response.data["data"]["allowed_actions"] == [
            "REQUEST_CHANGE", "RESCHEDULE", "CANCEL",
        ]

    def test_the_order_offers_the_edit_form_even_past_the_old_cutoff(
        self, customer_client, make_order
    ):
        order = _flag(make_order(pickup_date=_next(WEDNESDAY)), past_cutoff=True)

        response = customer_client.get(f"/api/customer/orders/{order.pk}/")

        assert response.status_code == 200
        data = response.data["data"]
        assert data["needs_new_pickup"] is True
        assert data["allowed_actions"] == ["MODIFY", "RESCHEDULE", "CANCEL"]

    def test_the_edit_form_moves_the_order(self, customer_client, make_order, make_slot, open_farmer):
        slot = make_slot(day_of_week=WEDNESDAY, start=time(10, 0), end=time(11, 0))
        new_day = _next(WEDNESDAY)
        order = _flag(make_order(pickup_date=new_day), past_cutoff=True)
        item = _item(order)

        response = customer_client.patch(
            f"/api/customer/orders/{order.pk}/",
            {
                "items": [{"product_id": item.product_id, "quantity": 2}],
                "pickup_slot_id": slot.pk,
                "pickup_date": new_day.isoformat(),
            },
            format="json",
            HTTP_IF_MATCH=f'"{order.version}"',
        )

        assert response.status_code == 200, response.data
        order.refresh_from_db()
        assert order.reschedule_requested_at is None
        assert order.pickup_slot_id == slot.pk
        assert timezone.localtime(order.pickup_start_at).time() == time(10, 0)

    def test_saving_without_a_new_time_says_what_is_missing(
        self, customer_client, make_order
    ):
        order = _flag(make_order(pickup_date=_next(WEDNESDAY)))

        response = customer_client.patch(
            f"/api/customer/orders/{order.pk}/", {"note": "see you"}, format="json",
            HTTP_IF_MATCH=f'"{order.version}"',
        )

        assert response.status_code == 400
        assert "pickup_slot_id" in response.data["errors"]
