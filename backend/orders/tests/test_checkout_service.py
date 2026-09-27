from datetime import datetime, time, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest import mock

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from accounts.exceptions import AccountLockedError
from notifications.models import Notification
from orders.exceptions import (
    CutoffPassedError,
    InsufficientStockError,
    OpenOrderLimitExceededError,
    ProductNotAvailableError,
    SlotNotAvailableError,
)
from orders.models import Order
from orders.services.checkout_service import expire_overdue_before_checkout, place_orders
PLACED_LIMIT_MESSAGE = (
    "You have 10 orders waiting for farmer confirmation. Please wait for them to be confirmed before placing more."
)

from tests_support.factories import make_customer, make_farmer, make_market, make_order, make_product, make_slot


@pytest.fixture
def shop(db):
    today = timezone.localdate()
    pickup_date = today + timedelta(days=3)
    market = make_market()
    farmer_a, farmer_b = make_farmer(), make_farmer()
    return SimpleNamespace(
        now=timezone.make_aware(datetime.combine(today, time(9, 0))),
        date=pickup_date,
        market=market,
        customer=make_customer(),
        farmer_a=farmer_a,
        farmer_b=farmer_b,
        slot_a=make_slot(farmer=farmer_a, market=market, day_of_week=pickup_date.isoweekday()),
        slot_b=make_slot(farmer=farmer_b, market=market, day_of_week=pickup_date.isoweekday()),
        tomato=make_product(farmer=farmer_a, stock=10, price="2.50"),
        herbs=make_product(farmer=farmer_a, stock=3, price="1.20"),
        eggs=make_product(farmer=farmer_b, stock=5, price="4.00"),
    )


def _group(farmer, slot, pickup_date, *items, note=None):
    return {
        "farmer_id": farmer.pk,
        "pickup_slot_id": slot.pk,
        "pickup_date": pickup_date,
        "note": note,
        "items": [{"product_id": product.pk, "quantity": quantity} for product, quantity in items],
    }


def _checkout(shop, *groups):
    # validate_pickup_date() and the held-stock query read the clock themselves, so freeze it at shop.now.
    with mock.patch("django.utils.timezone.now", return_value=shop.now):
        return place_orders(customer=shop.customer, groups=list(groups), now=shop.now)


def _real_past():
    # expire_overdue_orders() is called outside _checkout, with the real clock.
    return timezone.now() - timedelta(hours=1)


@pytest.mark.django_db
class TestPlaceOrders:
    def test_creates_one_placed_order_with_snapshots(self, shop):
        [order] = _checkout(shop, _group(shop.farmer_a, shop.slot_a, shop.date, (shop.tomato, 2), (shop.herbs, 1), note="Ring me"))

        shop.tomato.refresh_from_db()
        shop.herbs.refresh_from_db()
        start = timezone.make_aware(datetime.combine(shop.date, time(8, 0)))
        assert (order.status, order.version, order.customer_id, order.farmer_id) == ("PLACED", 1, shop.customer.id, shop.farmer_a.pk)
        assert (order.market_id, order.pickup_slot_id, order.stall_label) == (shop.market.id, shop.slot_a.id, "Row B, stall 12")
        assert (order.pickup_start_at, order.cutoff_at) == (start, start - timedelta(hours=12))
        assert (order.total_amount, order.note) == (Decimal("6.20"), "Ring me")
        items = {item.product_id: item for item in order.items.all()}
        assert (items[shop.tomato.id].unit_price, items[shop.tomato.id].line_total) == (Decimal("2.50"), Decimal("5.00"))
        assert items[shop.tomato.id].product_name == shop.tomato.name
        # v1.7 D-029: placing an order only checks stock; the farmer's acceptance (T2) takes it.
        assert (shop.tomato.stock_quantity, shop.herbs.stock_quantity) == (10, 3)
        history = order.status_history.get()
        assert (history.from_status, history.to_status, history.transition) == (None, "PLACED", "T1")
        assert (history.actor_id, history.actor_role) == (shop.customer.id, "CUSTOMER")
        assert Notification.objects.get(recipient=shop.farmer_a.user).type == "ORDER_PLACED"

    def test_creates_independent_orders_per_farmer(self, shop):
        orders = _checkout(
            shop,
            _group(shop.farmer_a, shop.slot_a, shop.date, (shop.tomato, 1)),
            _group(shop.farmer_b, shop.slot_b, shop.date, (shop.eggs, 2)),
        )

        assert [order.farmer_id for order in orders] == [shop.farmer_a.pk, shop.farmer_b.pk]
        assert [order.total_amount for order in orders] == [Decimal("2.50"), Decimal("8.00")]

    def test_all_or_nothing_reports_every_shortage(self, shop):
        shop.eggs.stock_quantity = 0
        shop.eggs.save()

        with pytest.raises(InsufficientStockError) as caught:
            _checkout(
                shop,
                _group(shop.farmer_a, shop.slot_a, shop.date, (shop.tomato, 1), (shop.herbs, 5)),
                _group(shop.farmer_b, shop.slot_b, shop.date, (shop.eggs, 1)),
            )

        assert caught.value.errors == {
            "groups.0.items.1.quantity": ["Only 3 KG left"],
            "groups.1.items.0.quantity": ["Out of stock"],
        }
        assert caught.value.data == {"available": {str(shop.herbs.id): 3, str(shop.eggs.id): 0}}
        shop.tomato.refresh_from_db()
        assert shop.tomato.stock_quantity == 10
        assert not Order.objects.exists()

    def test_several_orders_with_the_same_farmer_are_allowed(self, shop):
        # D-005 v1.5: a customer who forgot an item simply places another order with the same farmer.
        make_order(customer=shop.customer, product=shop.tomato)

        orders = _checkout(shop, _group(shop.farmer_a, shop.slot_a, shop.date, (shop.herbs, 1)))

        assert len(orders) == 1

    def test_at_most_ten_orders_waiting_for_confirmation(self, shop):
        for _ in range(10):
            make_order(customer=shop.customer, product=make_product(farmer=make_farmer()))

        with pytest.raises(OpenOrderLimitExceededError) as caught:
            _checkout(shop, _group(shop.farmer_a, shop.slot_a, shop.date, (shop.tomato, 1)))

        assert caught.value.errors == {"non_field_errors": [PLACED_LIMIT_MESSAGE]}

    def test_orders_about_to_be_created_count_towards_the_limit(self, shop):
        for _ in range(9):
            make_order(customer=shop.customer, product=make_product(farmer=make_farmer()))

        with pytest.raises(OpenOrderLimitExceededError):
            _checkout(
                shop,
                _group(shop.farmer_a, shop.slot_a, shop.date, (shop.tomato, 1)),
                _group(shop.farmer_b, shop.slot_b, shop.date, (shop.eggs, 1)),
            )

    @pytest.mark.parametrize("status", ["ACCEPTED", "READY_FOR_PICKUP"])
    def test_orders_already_confirmed_by_the_farmer_do_not_count(self, shop, status):
        for _ in range(10):
            make_order(customer=shop.customer, product=make_product(farmer=make_farmer()), status=status)

        orders = _checkout(shop, _group(shop.farmer_a, shop.slot_a, shop.date, (shop.tomato, 1)))

        assert len(orders) == 1

    def test_overdue_order_of_a_farmer_in_the_cart_does_not_count(self, shop):
        for _ in range(10):
            make_order(customer=shop.customer, product=shop.tomato, pickup_start_at=shop.now - timedelta(hours=1))

        orders = _checkout(shop, _group(shop.farmer_a, shop.slot_a, shop.date, (shop.herbs, 1)))

        assert len(orders) == 1

    def test_overdue_orders_with_farmers_outside_the_cart_do_not_count(self, shop):
        for _ in range(10):
            make_order(customer=shop.customer, product=make_product(farmer=make_farmer()),
                       pickup_start_at=shop.now - timedelta(hours=1))

        orders = _checkout(shop, _group(shop.farmer_a, shop.slot_a, shop.date, (shop.tomato, 1)))

        assert len(orders) == 1

    def test_placed_orders_of_other_customers_reduce_available_stock(self, shop):
        make_order(customer=make_customer(), product=shop.herbs, quantity=2)

        with pytest.raises(InsufficientStockError) as caught:
            _checkout(shop, _group(shop.farmer_a, shop.slot_a, shop.date, (shop.herbs, 2)))

        assert caught.value.errors == {"groups.0.items.0.quantity": ["Only 1 KG left"]}
        assert caught.value.data == {"available": {str(shop.herbs.id): 1}}

    def test_overdue_placed_order_holds_no_stock(self, shop):
        make_order(customer=make_customer(), product=shop.herbs, quantity=3, pickup_start_at=shop.now - timedelta(hours=1))

        _checkout(shop, _group(shop.farmer_a, shop.slot_a, shop.date, (shop.herbs, 2)))

        shop.herbs.refresh_from_db()
        assert shop.herbs.stock_quantity == 3

    @pytest.mark.parametrize("status", ["ACCEPTED", "READY_FOR_PICKUP"])
    def test_accepted_orders_are_already_out_of_stock_and_not_held_twice(self, shop, status):
        make_order(customer=make_customer(), product=shop.herbs, quantity=2, status=status)

        orders = _checkout(shop, _group(shop.farmer_a, shop.slot_a, shop.date, (shop.herbs, 3)))

        assert len(orders) == 1

    def test_locked_customer_cannot_place_orders(self, shop):
        shop.customer.is_active = False
        shop.customer.save()
        shop.customer.customer_profile.deactivation_reason = "Repeated no-shows"
        shop.customer.customer_profile.save()

        with pytest.raises(AccountLockedError) as caught:
            _checkout(shop, _group(shop.farmer_a, shop.slot_a, shop.date, (shop.tomato, 1)))
        assert caught.value.errors == {"reason": ["Repeated no-shows"]}
        assert not Order.objects.exists()

    def test_product_of_another_farmer_is_a_validation_error(self, shop):
        with pytest.raises(ValidationError) as caught:
            _checkout(shop, _group(shop.farmer_a, shop.slot_a, shop.date, (shop.eggs, 1)))

        assert "groups.0.items.0.product_id" in caught.value.detail

    @pytest.mark.parametrize("field, value", [("is_archived", True), ("is_hidden_by_admin", True), ("is_available", False)])
    def test_unpublished_product_is_not_available(self, shop, field, value):
        setattr(shop.tomato, field, value)
        shop.tomato.save()

        with pytest.raises(ProductNotAvailableError) as caught:
            _checkout(shop, _group(shop.farmer_a, shop.slot_a, shop.date, (shop.tomato, 1)))

        assert "groups.0.items.0.product_id" in caught.value.errors

    def test_unapproved_farmer_is_not_available(self, shop):
        shop.farmer_a.status = "SUSPENDED"
        shop.farmer_a.save()

        with pytest.raises(ProductNotAvailableError) as caught:
            _checkout(shop, _group(shop.farmer_a, shop.slot_a, shop.date, (shop.tomato, 1)))

        assert "groups.0.farmer_id" in caught.value.errors

    @pytest.mark.parametrize("review_status", ["PENDING", "REJECTED"])
    def test_a_listing_not_approved_by_an_admin_cannot_be_ordered(self, shop, review_status):
        shop.tomato.review_status = review_status
        shop.tomato.save()

        with pytest.raises(ProductNotAvailableError) as caught:
            _checkout(shop, _group(shop.farmer_a, shop.slot_a, shop.date, (shop.tomato, 1)))

        assert "groups.0.items.0.product_id" in caught.value.errors

    def test_a_line_above_the_stall_cap_is_rejected_on_that_line(self, shop):
        shop.tomato.max_per_order = 2
        shop.tomato.save()

        with pytest.raises(ValidationError) as caught:
            _checkout(shop, _group(shop.farmer_a, shop.slot_a, shop.date, (shop.herbs, 1), (shop.tomato, 3)))

        assert "at most 2 kg" in str(caught.value.detail["groups.0.items.1.quantity"][0])
        assert Order.objects.count() == 0

    def test_a_line_at_the_stall_cap_is_accepted(self, shop):
        shop.tomato.max_per_order = 2
        shop.tomato.save()

        [order] = _checkout(shop, _group(shop.farmer_a, shop.slot_a, shop.date, (shop.tomato, 2)))

        assert order.items.get().quantity == 2

    def test_a_line_below_the_stall_minimum_is_rejected_and_the_minimum_itself_is_accepted(self, shop):
        shop.tomato.min_per_order = 3
        shop.tomato.save()

        with pytest.raises(ValidationError) as caught:
            _checkout(shop, _group(shop.farmer_a, shop.slot_a, shop.date, (shop.tomato, 2)))
        assert "minimum" in str(caught.value.detail["groups.0.items.0.quantity"][0])

        [order] = _checkout(shop, _group(shop.farmer_a, shop.slot_a, shop.date, (shop.tomato, 3)))
        assert order.items.get().quantity == 3

    def test_invalid_slot_points_at_the_group(self, shop):
        with pytest.raises(SlotNotAvailableError) as caught:
            _checkout(shop, _group(shop.farmer_a, shop.slot_a, shop.date + timedelta(days=1), (shop.tomato, 1)))

        assert "groups.0.pickup_slot_id" in caught.value.errors

    def test_day_the_farmer_does_not_operate_points_at_the_group(self, shop):
        shop.farmer_a.operating_days = [day for day in range(1, 8) if day != shop.date.isoweekday()]
        shop.farmer_a.save()

        with pytest.raises(SlotNotAvailableError) as caught:
            _checkout(shop, _group(shop.farmer_a, shop.slot_a, shop.date, (shop.tomato, 1)))

        assert "groups.0.pickup_slot_id" in caught.value.errors

    def test_past_cutoff_is_rejected(self, shop):
        shop.now = timezone.make_aware(datetime.combine(shop.date, time(8, 0))) - timedelta(hours=1)

        with pytest.raises(CutoffPassedError):
            _checkout(shop, _group(shop.farmer_a, shop.slot_a, shop.date, (shop.tomato, 1)))


@pytest.mark.django_db
class TestExpireOverdueBeforeCheckout:
    def test_expires_overdue_orders_of_the_cart_farmers_only(self, shop):
        mine = make_order(customer=make_customer(), product=shop.tomato, pickup_start_at=_real_past())
        elsewhere = make_order(customer=make_customer(), product=make_product(farmer=make_farmer()),
                               pickup_start_at=_real_past())

        expire_overdue_before_checkout(farmer_ids=[shop.farmer_a.pk, shop.farmer_b.pk])

        mine.refresh_from_db()
        elsewhere.refresh_from_db()
        shop.tomato.refresh_from_db()
        assert (mine.status, elsewhere.status) == ("EXPIRED", "PLACED")
        assert shop.tomato.stock_quantity == 10
