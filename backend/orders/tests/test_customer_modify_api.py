from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.auth.tokens import issue_tokens
from markets.models import FarmerMarket
from notifications.models import Notification
from tests_support.factories import make_customer, make_farmer, make_market, make_order, make_product, make_slot


def _client(user) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
    return client


def _url(order) -> str:
    return f"/api/customer/orders/{order.pk}/"


def _patch(client, order, body, version=None):
    headers = {} if version is False else {"HTTP_IF_MATCH": str(order.version if version is None else version)}
    return client.patch(_url(order), body, format="json", **headers)


@pytest.fixture
def shop(db):
    farmer = make_farmer()
    customer = make_customer()
    market = make_market()
    FarmerMarket.objects.create(farmer=farmer, market=market, stall_label="Row B, stall 12")
    return SimpleNamespace(
        customer=customer, api=_client(customer), farmer=farmer, market=market,
        tomato=make_product(farmer=farmer, stock=10, price="2.50"),
        herbs=make_product(farmer=farmer, stock=5, price="3.00"),
    )


def _order(shop, **kwargs):
    return make_order(customer=shop.customer, product=shop.tomato, market=shop.market, **kwargs)


def _items(*pairs):
    return {"items": [{"product_id": product.pk, "quantity": quantity} for product, quantity in pairs]}


@pytest.mark.django_db
class TestModifyPlacedOrder:
    def test_items_change_in_place_keeping_old_prices(self, shop):
        order = _order(shop, quantity=2)
        shop.tomato.price = Decimal("9.99")
        shop.tomato.save()

        response = _patch(shop.api, order, _items((shop.tomato, 4), (shop.herbs, 1)))

        assert response.status_code == 200
        data = response.json()["data"]
        lines = {item["product_id"]: (item["quantity"], item["unit_price"]) for item in data["items"]}
        assert lines == {shop.tomato.pk: (4, "2.50"), shop.herbs.pk: (1, "3.00")}
        assert (data["status"], data["version"], data["total_amount"]) == ("PLACED", 2, "13.00")
        assert data["pending_change"] is None
        change = data["status_history"][-1]
        assert (change["from_status"], change["to_status"], change["transition"]) == ("PLACED", "PLACED", None)
        assert change["change_reason"].startswith("Customer modified:")
        shop.tomato.refresh_from_db()
        assert shop.tomato.stock_quantity == 10
        assert Notification.objects.get(recipient=shop.farmer.user).type == "ORDER_MODIFIED"

    def test_reschedule_recomputes_the_pickup_window(self, shop):
        order = _order(shop)
        new_date = timezone.localdate() + timedelta(days=4)
        slot = make_slot(farmer=shop.farmer, market=shop.market, day_of_week=new_date.isoweekday())

        response = _patch(shop.api, order, {"pickup_slot_id": slot.pk, "pickup_date": new_date.isoformat()})

        assert response.status_code == 200
        data = response.json()["data"]
        assert (data["pickup_date"], data["pickup_slot_id"], data["stall_label"]) == (
            new_date.isoformat(), slot.pk, "Row B, stall 12"
        )

    def test_day_the_farmer_does_not_operate_is_rejected(self, shop):
        order = _order(shop)
        new_date = timezone.localdate() + timedelta(days=4)
        slot = make_slot(farmer=shop.farmer, market=shop.market, day_of_week=new_date.isoweekday())
        shop.farmer.operating_days = [day for day in range(1, 8) if day != new_date.isoweekday()]
        shop.farmer.save()

        response = _patch(shop.api, order, {"pickup_slot_id": slot.pk, "pickup_date": new_date.isoformat()})

        assert (response.status_code, response.json()["code"]) == (422, "SLOT_NOT_AVAILABLE")

    def test_date_beyond_the_booking_horizon_is_rejected(self, shop):
        order = _order(shop)
        new_date = timezone.localdate() + timedelta(days=7)
        slot = make_slot(farmer=shop.farmer, market=shop.market, day_of_week=new_date.isoweekday())

        response = _patch(shop.api, order, {"pickup_slot_id": slot.pk, "pickup_date": new_date.isoformat()})

        assert (response.status_code, response.json()["code"]) == (422, "SLOT_NOT_AVAILABLE")


@pytest.mark.django_db
class TestChangeRequestForAcceptedOrder:
    def test_order_stays_as_it_is_and_the_request_is_shown(self, shop):
        order = _order(shop, quantity=2, status="ACCEPTED")

        response = _patch(shop.api, order, _items((shop.tomato, 3), (shop.herbs, 1)))

        assert response.status_code == 200
        data = response.json()["data"]
        assert [(item["product_id"], item["quantity"]) for item in data["items"]] == [(shop.tomato.pk, 2)]
        assert (data["status"], data["version"], data["has_pending_change"]) == ("ACCEPTED", 2, True)
        assert data["allowed_actions"] == ["REQUEST_CHANGE", "CANCEL"]
        pending = data["pending_change"]
        assert pending["items"] == [
            {"product_id": shop.tomato.pk, "product_name": shop.tomato.name, "unit": "KG", "quantity": 3,
             "current_quantity": 2, "stock_available": 10, "unit_price": "2.50"},
            {"product_id": shop.herbs.pk, "product_name": shop.herbs.name, "unit": "KG", "quantity": 1,
             "current_quantity": 0, "stock_available": 5, "unit_price": "3.00"},
        ]
        assert pending["estimated_total"] == "10.50"
        assert (pending["pickup_slot_id"], pending["pickup_date"], pending["pickup_start_at"]) == (None, None, None)
        assert pending["requested_at"]
        assert pending["expires_at"] == data["pickup_start_at"]
        assert data["status_history"][-1]["change_reason"].startswith("Change request submitted:")

    def test_estimate_keeps_the_prices_the_customer_saw(self, shop):
        # v1.8: kept items keep their order price, new items the price at request time.
        order = _order(shop, quantity=2, status="ACCEPTED")
        _patch(shop.api, order, _items((shop.tomato, 3), (shop.herbs, 1)))
        shop.tomato.price = shop.herbs.price = Decimal("9.99")
        shop.tomato.save()
        shop.herbs.save()

        pending = shop.api.get(_url(order)).json()["data"]["pending_change"]

        assert pending["estimated_total"] == "10.50"

    def test_a_new_request_replaces_the_previous_one(self, shop):
        order = _order(shop, quantity=2, status="ACCEPTED")
        _patch(shop.api, order, _items((shop.tomato, 3)))
        order.refresh_from_db()

        response = _patch(shop.api, order, _items((shop.tomato, 1)))

        assert [item["quantity"] for item in response.json()["data"]["pending_change"]["items"]] == [1]

    def test_rescheduling_request_shows_the_new_window(self, shop):
        order = _order(shop, status="ACCEPTED")
        new_date = timezone.localdate() + timedelta(days=4)
        slot = make_slot(farmer=shop.farmer, market=shop.market, day_of_week=new_date.isoweekday())

        pending = _patch(shop.api, order, {"pickup_slot_id": slot.pk, "pickup_date": new_date.isoformat()}).json()[
            "data"]["pending_change"]

        assert (pending["pickup_slot_id"], pending["pickup_date"]) == (slot.pk, new_date.isoformat())
        assert pending["pickup_start_at"] and pending["pickup_end_at"] and pending["cutoff_at"]
        assert pending["items"] is None  # v1.8: items unchanged


@pytest.mark.django_db
class TestModifyErrors:
    def test_if_match_is_required(self, shop):
        response = _patch(shop.api, _order(shop), _items((shop.tomato, 1)), version=False)

        assert (response.status_code, response.json()["code"]) == (428, "PRECONDITION_REQUIRED")

    def test_stale_version_is_rejected(self, shop):
        response = _patch(shop.api, _order(shop), _items((shop.tomato, 1)), version=9)

        assert (response.status_code, response.json()["code"]) == (409, "RESOURCE_MODIFIED")

    def test_after_cutoff_is_rejected(self, shop):
        order = _order(shop, pickup_start_at=timezone.now() + timedelta(hours=6))

        response = _patch(shop.api, order, _items((shop.tomato, 1)))

        assert (response.status_code, response.json()["code"]) == (422, "CUTOFF_PASSED")

    def test_finished_order_cannot_be_modified(self, shop):
        response = _patch(shop.api, _order(shop, status="COMPLETED"), _items((shop.tomato, 1)))

        assert (response.status_code, response.json()["code"]) == (400, "INVALID_STATUS_TRANSITION")

    def test_another_customers_order_is_not_found(self, shop):
        other = make_order(customer=make_customer(), product=shop.tomato)

        assert _patch(shop.api, other, _items((shop.tomato, 1))).status_code == 404

    def test_not_enough_stock_for_the_increase(self, shop):
        response = _patch(shop.api, _order(shop, quantity=2), _items((shop.tomato, 2), (shop.herbs, 6)))

        assert (response.status_code, response.json()["code"]) == (400, "INSUFFICIENT_STOCK")

    def test_hidden_product_cannot_be_increased(self, shop):
        order = _order(shop, quantity=2)
        shop.tomato.is_hidden_by_admin = True
        shop.tomato.save()

        response = _patch(shop.api, order, _items((shop.tomato, 3)))

        assert (response.status_code, response.json()["code"]) == (422, "PRODUCT_NOT_AVAILABLE")

    @pytest.mark.parametrize("body", [
        {"items": []},
        {"items": [{"product_id": 1, "quantity": 1}, {"product_id": 1, "quantity": 2}]},
        {"pickup_date": "2030-01-01"},
        {},
    ])
    def test_malformed_body_is_rejected(self, shop, body):
        response = _patch(shop.api, _order(shop), body)

        assert (response.status_code, response.json()["code"]) == (400, "VALIDATION_ERROR")

    def test_farmer_is_forbidden(self, shop):
        assert _patch(_client(shop.farmer.user), _order(shop), _items((shop.tomato, 1))).status_code == 403

    def test_other_farmers_product_is_rejected(self, shop):
        foreign = make_product(farmer=make_farmer())

        response = _patch(shop.api, _order(shop), _items((foreign, 1)))

        assert (response.status_code, response.json()["code"]) == (422, "PRODUCT_NOT_AVAILABLE")
