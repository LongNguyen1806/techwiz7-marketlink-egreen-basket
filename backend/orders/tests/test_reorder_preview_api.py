from decimal import Decimal
from types import SimpleNamespace

import pytest
from rest_framework.test import APIClient

from accounts.auth.tokens import issue_tokens
from accounts.models import FarmerStatus
from orders.models import Order, OrderItem, OrderStatus
from tests_support.factories import make_customer, make_farmer, make_market, make_order, make_product

PRODUCT_KEYS = {
    "id", "name", "image", "price", "unit", "stock_quantity", "min_per_order", "max_per_order", "is_available", "availability",
    "category", "farmer", "rating_avg", "rating_count", "is_favorite",
}


def _client(user) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
    return client


def _url(order) -> str:
    return f"/api/customer/orders/{order.pk}/reorder-preview/"


@pytest.fixture
def shop(db):
    customer = make_customer()
    farmer = make_farmer()
    return SimpleNamespace(
        customer=customer, api=_client(customer), farmer=farmer, market=make_market(),
        tomato=make_product(farmer=farmer, stock=10, price="2.50"),
        herbs=make_product(farmer=farmer, stock=5, price="3.00"),
    )


def _completed_order(shop, *pairs) -> Order:
    """A finished order holding the given (product, quantity) lines at their price back then."""
    order = make_order(customer=shop.customer, product=pairs[0][0], quantity=pairs[0][1],
                       status=OrderStatus.COMPLETED, market=shop.market)
    for product, quantity in pairs[1:]:
        OrderItem.objects.create(
            order=order, product=product, product_name=product.name, unit=product.unit,
            unit_price=product.price, quantity=quantity, line_total=product.price * quantity,
        )
    return order


def _data(shop, order) -> dict:
    response = shop.api.get(_url(order))
    assert response.status_code == 200, response.json()
    return response.json()["data"]


@pytest.mark.django_db
class TestReorderPreview:
    def test_returns_current_prices_and_the_old_quantities(self, shop):
        order = _completed_order(shop, (shop.tomato, 2), (shop.herbs, 3))
        shop.tomato.price = Decimal("4.75")  # the farmer raised the price after that order
        shop.tomato.save()

        data = _data(shop, order)

        assert set(data) == {"items", "skipped"}
        assert data["skipped"] == []
        lines = {row["product"]["id"]: row for row in data["items"]}
        assert set(lines[shop.tomato.pk]["product"]) == PRODUCT_KEYS
        assert (lines[shop.tomato.pk]["product"]["price"], lines[shop.tomato.pk]["quantity"]) == ("4.75", 2)
        assert (lines[shop.herbs.pk]["product"]["price"], lines[shop.herbs.pk]["quantity"]) == ("3.00", 3)

    @pytest.mark.parametrize("overrides", [{"is_archived": True}, {"is_hidden_by_admin": True}, {"is_available": False}])
    def test_a_product_no_longer_on_sale_is_skipped(self, shop, overrides):
        order = _completed_order(shop, (shop.tomato, 2), (shop.herbs, 1))
        for field, value in overrides.items():
            setattr(shop.tomato, field, value)
        shop.tomato.save()

        data = _data(shop, order)

        assert [row["product"]["id"] for row in data["items"]] == [shop.herbs.pk]
        assert data["skipped"] == [
            {"product_id": shop.tomato.pk, "product_name": shop.tomato.name, "reason": "UNAVAILABLE"}
        ]

    def test_a_product_of_a_suspended_farmer_is_skipped(self, shop):
        order = _completed_order(shop, (shop.tomato, 1))
        shop.farmer.status = FarmerStatus.SUSPENDED
        shop.farmer.save()

        data = _data(shop, order)

        assert data["items"] == []
        assert data["skipped"][0]["reason"] == "UNAVAILABLE"

    def test_a_sold_out_product_is_skipped(self, shop):
        order = _completed_order(shop, (shop.tomato, 2), (shop.herbs, 1))
        shop.tomato.stock_quantity = 0
        shop.tomato.save()

        data = _data(shop, order)

        assert [row["product"]["id"] for row in data["items"]] == [shop.herbs.pk]
        assert data["skipped"] == [
            {"product_id": shop.tomato.pk, "product_name": shop.tomato.name, "reason": "OUT_OF_STOCK"}
        ]

    def test_stock_held_by_someone_elses_placed_order_counts_as_sold_out(self, shop):
        # D-029: available stock is stock_quantity minus what PLACED orders hold, as checkout computes it.
        order = _completed_order(shop, (shop.herbs, 1))
        make_order(customer=make_customer(), product=shop.herbs, quantity=5)

        data = _data(shop, order)

        assert data["items"] == []
        assert data["skipped"][0]["reason"] == "OUT_OF_STOCK"

    def test_nothing_can_be_reordered(self, shop):
        order = _completed_order(shop, (shop.tomato, 1))
        shop.tomato.is_archived = True
        shop.tomato.save()

        data = _data(shop, order)

        assert (data["items"], len(data["skipped"])) == ([], 1)

    def test_the_preview_writes_nothing(self, shop):
        order = _completed_order(shop, (shop.tomato, 2))
        before = (Order.objects.count(), OrderItem.objects.count(), order.version)

        _data(shop, order)

        order.refresh_from_db()
        assert (Order.objects.count(), OrderItem.objects.count(), order.version) == before

    def test_works_for_an_open_order_too(self, shop):
        # The API is gated on ownership only; C-04 decides where the Reorder button appears.
        order = make_order(customer=shop.customer, product=shop.tomato, market=shop.market)

        assert len(_data(shop, order)["items"]) == 1

    def test_another_customers_order_is_not_found(self, shop):
        other = make_order(customer=make_customer(), product=shop.tomato, market=shop.market)

        assert shop.api.get(_url(other)).status_code == 404

    def test_farmer_is_forbidden(self, shop):
        order = _completed_order(shop, (shop.tomato, 1))

        assert _client(shop.farmer.user).get(_url(order)).status_code == 403

    def test_requires_login(self, shop):
        order = _completed_order(shop, (shop.tomato, 1))

        assert APIClient().get(_url(order)).status_code == 401

    def test_query_count_does_not_grow_with_the_number_of_lines(self, shop, django_assert_max_num_queries):
        pairs = [(shop.tomato, 1), (shop.herbs, 1)] + [
            (make_product(farmer=shop.farmer, stock=3), 2) for _ in range(4)
        ]
        order = _completed_order(shop, *pairs)

        with django_assert_max_num_queries(10):
            assert len(_data(shop, order)["items"]) == 6
