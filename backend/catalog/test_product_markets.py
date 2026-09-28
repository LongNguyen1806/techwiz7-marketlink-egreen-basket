from datetime import timedelta

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from catalog.models import Product, ProductMarketExclusion, ReviewStatus, Unit
from catalog.selectors import markets_for_products, public_products
from markets.models import FarmerMarket, PickupSlot
from orders.exceptions import ProductNotAvailableError
from orders.services.checkout_service import _validate_markets
from orders.services.modify import modify_order
from orders.services.pickup_service import PickupWindow, _active_slots
from marketlink_core.exceptions import UnprocessableEntityError

PRODUCTS_URL = "/api/farmer/products/"


@pytest.fixture
def farmer_client(farmer_user):
    client = APIClient()
    client.force_authenticate(user=farmer_user)
    return client


@pytest.fixture
def central_stall(seller_market, approved_farmer):
    return FarmerMarket.objects.get(farmer=approved_farmer, market=seller_market)


@pytest.fixture
def home_stall(approved_farmer):
    return FarmerMarket.objects.get(farmer=approved_farmer, market__name="Home Market")


def _exclude(product, stall):
    ProductMarketExclusion.objects.create(product=product, farmer_market=stall)


@pytest.mark.django_db
def test_a_product_is_sold_at_every_approved_market_by_default(product, seller_market):
    assert list(public_products(market_id=seller_market.id)) == [product]
    assert [m["market_id"] for m in markets_for_products(product_ids=[product.id])[product.id]] == [
        seller_market.id
    ]


@pytest.mark.django_db
def test_an_excluded_market_drops_out_of_the_filters_and_the_detail(
    product, seller_market, central_stall
):
    _exclude(product, central_stall)

    assert list(public_products(market_id=seller_market.id)) == []
    assert list(public_products(day=1)) == []
    assert product.id not in markets_for_products(product_ids=[product.id])
    assert list(public_products()) == [product]


@pytest.mark.django_db
def test_a_product_sold_nowhere_is_not_public(product, central_stall, home_stall):
    _exclude(product, central_stall)
    _exclude(product, home_stall)

    assert list(public_products()) == []


@pytest.mark.django_db
def test_pickup_slots_skip_markets_a_cart_item_is_not_sold_at(
    approved_farmer, product, central_stall
):
    assert _active_slots(approved_farmer, [product.id]).exists()

    _exclude(product, central_stall)

    assert not _active_slots(approved_farmer, [product.id]).exists()
    assert _active_slots(approved_farmer).exists()


@pytest.mark.django_db
def test_checkout_refuses_an_item_at_a_market_it_is_not_sold_at(product, central_stall):
    _exclude(product, central_stall)
    slot = PickupSlot.objects.filter(farmer_market=central_stall, is_active=True).first()
    start = timezone.now() + timedelta(days=2)
    window = PickupWindow(
        slot=slot,
        pickup_date=start.date(),
        pickup_start_at=start,
        pickup_end_at=start + timedelta(hours=2),
        cutoff_at=start - timedelta(hours=12),
    )
    groups = [{"farmer_id": product.farmer_id, "items": [{"product_id": product.id, "quantity": 1}]}]

    with pytest.raises(ProductNotAvailableError) as caught:
        _validate_markets(groups, [window], {product.id: product})

    assert "is not sold at Central Market" in str(caught.value.errors)


@pytest.mark.django_db
def test_an_order_cannot_grow_with_an_item_not_sold_at_its_market(
    product, central_stall, make_order_with_item, customer_user
):
    order = make_order_with_item(product=product, quantity=2, days_ahead=3)
    _exclude(product, central_stall)

    with pytest.raises(UnprocessableEntityError):
        modify_order(
            order_id=order.id,
            actor=customer_user,
            expected_version=order.version,
            items_data=[{"product_id": product.id, "quantity": 3}],
        )


@pytest.mark.django_db
def test_a_farmer_chooses_where_a_new_product_is_sold(
    farmer_client, category, seller_market, central_stall, home_stall
):
    response = farmer_client.post(
        PRODUCTS_URL,
        {
            "name": "Cucumber",
            "category_id": category.id,
            "price": "1.50",
            "unit": "KG",
            "stock_quantity": 10,
            "market_ids": [seller_market.id],
        },
        format="json",
    )

    assert response.status_code == 201
    product = Product.objects.get(name="Cucumber")
    assert list(ProductMarketExclusion.objects.filter(product=product).values_list("farmer_market_id", flat=True)) == [
        home_stall.id
    ]
    assert [m["market_id"] for m in response.data["data"]["markets"]] == [seller_market.id]


@pytest.mark.django_db
def test_markets_must_be_approved_and_not_empty(farmer_client, category, approved_farmer, market_waiting):
    body = {"name": "Cucumber", "category_id": category.id, "price": "1.50", "unit": "KG", "stock_quantity": 10}

    assert farmer_client.post(PRODUCTS_URL, {**body, "market_ids": []}, format="json").status_code == 400
    refused = farmer_client.post(PRODUCTS_URL, {**body, "market_ids": [market_waiting.market_id]}, format="json")
    assert refused.status_code == 400
    assert "market_ids" in refused.data["errors"]
    assert not Product.objects.filter(name="Cucumber").exists()


@pytest.fixture
def market_waiting(approved_farmer):
    from datetime import time

    from markets.models import FarmerMarketStatus, Market

    market = Market.objects.create(
        name="Waiting Market", address="5 Wait Road", latitude="10.9", longitude="106.9",
        open_time=time(6, 0), close_time=time(12, 0),
    )
    return FarmerMarket.objects.create(
        farmer=approved_farmer, market=market, stall_label="W1", status=FarmerMarketStatus.PENDING
    )


@pytest.mark.django_db
def test_editing_the_markets_moves_the_product(farmer_client, product, seller_market, central_stall, home_stall):
    response = farmer_client.patch(
        f"{PRODUCTS_URL}{product.id}/", {"market_ids": [home_stall.market_id]}, format="json"
    )

    assert response.status_code == 200
    assert list(public_products(market_id=seller_market.id)) == []
    product.refresh_from_db()
    assert product.review_status == ReviewStatus.APPROVED


@pytest.mark.django_db
def test_the_list_filters_by_market_and_the_counts_follow(
    farmer_client, product, category, approved_farmer, seller_market, central_stall
):
    other = Product.objects.create(
        farmer=approved_farmer, category=category, name="Carrot", price="1.00", unit=Unit.KG,
        stock_quantity=0, review_status=ReviewStatus.PENDING,
    )
    _exclude(other, central_stall)

    listed = farmer_client.get(PRODUCTS_URL, {"market_id": seller_market.id}).data["data"]["results"]
    counts = farmer_client.get(f"{PRODUCTS_URL}counts/").data["data"]
    counts_here = farmer_client.get(f"{PRODUCTS_URL}counts/", {"market_id": seller_market.id}).data["data"]

    assert [row["id"] for row in listed] == [product.id]
    assert counts["all"] == 2 and counts["in_stock"] == 1 and counts["in_review"] == 1
    assert counts_here["all"] == 1 and counts_here["in_review"] == 0


@pytest.mark.django_db
def test_bulk_actions_touch_only_the_farmers_own_products(
    farmer_client, product, category, approved_farmer, seller_market, make_farmer
):
    stranger = make_farmer(email="stranger@marketlink.test", stall_name="Stranger")
    foreign = Product.objects.create(
        farmer=stranger, category=category, name="Foreign", price="1.00", unit=Unit.KG, stock_quantity=5,
    )
    url = f"{PRODUCTS_URL}bulk/"

    paused = farmer_client.post(url, {"product_ids": [product.id, foreign.id], "action": "pause"}, format="json")
    sold_out = farmer_client.post(url, {"product_ids": [product.id], "action": "sold_out"}, format="json")
    moved = farmer_client.post(
        url, {"product_ids": [product.id], "action": "set_markets", "market_ids": [seller_market.id]}, format="json"
    )

    assert paused.data["data"]["updated"] == 1
    assert sold_out.data["data"]["updated"] == 1
    assert moved.data["data"]["updated"] == 1
    product.refresh_from_db()
    foreign.refresh_from_db()
    assert product.is_available is False and product.stock_quantity == 0
    assert foreign.is_available is True
    assert farmer_client.post(url, {"product_ids": [product.id], "action": "set_markets"}, format="json").status_code == 400
