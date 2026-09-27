import pytest
from django.urls import reverse

from accounts.models import FarmerStatus
from catalog.models import Category, Product, ReviewStatus, Unit
from catalog.selectors import MAX_CART_REFRESH_IDS
from favorites.models import FavoriteProduct

CATEGORIES_URL = "public-category-list"
PRODUCTS_URL = "public-product-list"
PRODUCT_URL = "public-product-detail"


@pytest.fixture
def other_category(db):
    return Category.objects.create(name="Fruit", display_order=2)


@pytest.fixture
def make_product(category, approved_farmer):
    def _make(*, name, price="2.00", stock=5, **overrides) -> Product:
        return Product.objects.create(
            farmer=approved_farmer,
            category=overrides.pop("category", category),
            name=name,
            price=price,
            unit=Unit.KG,
            stock_quantity=stock,
            # These stand for listings already on sale. A fresh Product() is PENDING, which
            # is the right default for the model and the wrong one for a shopper's view.
            review_status=overrides.pop("review_status", ReviewStatus.APPROVED),
            **overrides,
        )

    return _make


@pytest.mark.django_db
def test_categories_are_a_plain_active_only_list(api_client, category):
    Category.objects.create(name="Hidden", display_order=9, is_active=False)

    response = api_client.get(reverse(CATEGORIES_URL))

    assert response.status_code == 200
    rows = response.data["data"]
    # PU-02 has no [P] marker.
    assert isinstance(rows, list)
    assert [row["name"] for row in rows] == ["Vegetables"]
    assert set(rows[0]) == {"id", "name", "icon", "display_order"}


@pytest.mark.django_db
def test_a_guest_sees_only_publicly_sellable_products(api_client, product, make_product):
    make_product(name="Archived", is_archived=True)
    make_product(name="Removed by admin", is_hidden_by_admin=True)

    rows = api_client.get(reverse(PRODUCTS_URL)).data["data"]["results"]

    assert [row["name"] for row in rows] == ["Tomato"]
    assert rows[0]["price"] == "2.50"
    assert rows[0]["availability"] == "IN_STOCK"
    assert rows[0]["is_favorite"] is None


@pytest.mark.django_db
def test_products_of_a_suspended_farmer_disappear(api_client, product, approved_farmer):
    approved_farmer.status = FarmerStatus.SUSPENDED
    approved_farmer.save(update_fields=["status"])

    assert api_client.get(reverse(PRODUCTS_URL)).data["data"]["count"] == 0
    assert api_client.get(reverse(PRODUCT_URL, args=[product.id])).status_code == 404


@pytest.mark.django_db
def test_products_of_a_disabled_account_disappear(api_client, product, approved_farmer):
    user = approved_farmer.user
    user.is_active = False
    user.save(update_fields=["is_active"])

    assert api_client.get(reverse(PRODUCTS_URL)).data["data"]["count"] == 0


@pytest.mark.django_db
def test_in_stock_defaults_to_true(api_client, make_product):
    make_product(name="Available", stock=3)
    make_product(name="Sold out", stock=0)
    make_product(name="Paused", stock=4, is_available=False)

    default = api_client.get(reverse(PRODUCTS_URL)).data["data"]
    assert [row["name"] for row in default["results"]] == ["Available"]

    everything = api_client.get(reverse(PRODUCTS_URL), {"in_stock": "false"}).data["data"]
    assert everything["count"] == 3
    rows = {row["name"]: row for row in everything["results"]}
    assert rows["Sold out"]["availability"] == "OUT_OF_STOCK"
    assert rows["Paused"]["availability"] == "UNAVAILABLE"


@pytest.mark.django_db
def test_the_ids_parameter_ignores_in_stock_for_the_cart(api_client, make_product):
    sold_out = make_product(name="Sold out", stock=0)
    archived = make_product(name="Archived", is_archived=True)

    rows = api_client.get(
        reverse(PRODUCTS_URL), {"ids": f"{sold_out.id},{archived.id}"}
    ).data["data"]["results"]

    # Refreshing the cart keeps sold-out rows so they can be marked Unavailable, but an
    # archived product is gone for good.
    assert [row["name"] for row in rows] == ["Sold out"]


@pytest.mark.django_db
def test_the_ids_parameter_is_capped(api_client, make_product):
    products = [make_product(name=f"Product {index}") for index in range(MAX_CART_REFRESH_IDS + 5)]
    ids = ",".join(str(p.id) for p in products)

    count = api_client.get(reverse(PRODUCTS_URL), {"ids": ids}).data["data"]["count"]

    assert count == MAX_CART_REFRESH_IDS


@pytest.mark.django_db
def test_rubbish_in_ids_is_skipped_rather_than_failing(api_client, product):
    rows = api_client.get(reverse(PRODUCTS_URL), {"ids": f"abc,{product.id},"}).data["data"]

    assert rows["count"] == 1


@pytest.mark.django_db
def test_filters_by_category_price_and_farmer(
    api_client, make_product, other_category, approved_farmer
):
    make_product(name="Cheap veg", price="1.00")
    make_product(name="Pricey fruit", price="9.00", category=other_category)

    by_category = api_client.get(reverse(PRODUCTS_URL), {"category": str(other_category.id)})
    assert [r["name"] for r in by_category.data["data"]["results"]] == ["Pricey fruit"]

    by_price = api_client.get(reverse(PRODUCTS_URL), {"price_min": "5", "price_max": "10"})
    assert [r["name"] for r in by_price.data["data"]["results"]] == ["Pricey fruit"]

    by_farmer = api_client.get(reverse(PRODUCTS_URL), {"farmer_id": approved_farmer.user_id})
    assert by_farmer.data["data"]["count"] == 2

    assert api_client.get(reverse(PRODUCTS_URL), {"farmer_id": "9999"}).data["data"]["count"] == 0


@pytest.mark.django_db
def test_search_matches_product_or_stall_name(api_client, product):
    assert api_client.get(reverse(PRODUCTS_URL), {"q": "toma"}).data["data"]["count"] == 1
    assert api_client.get(reverse(PRODUCTS_URL), {"q": "Test Stall"}).data["data"]["count"] == 1


@pytest.mark.django_db
def test_price_ordering(api_client, make_product):
    make_product(name="Mid", price="5.00")
    make_product(name="Low", price="1.00")
    make_product(name="High", price="9.00")

    ascending = api_client.get(reverse(PRODUCTS_URL), {"ordering": "price_asc"})
    assert [r["name"] for r in ascending.data["data"]["results"]] == ["Low", "Mid", "High"]

    descending = api_client.get(reverse(PRODUCTS_URL), {"ordering": "price_desc"})
    assert [r["name"] for r in descending.data["data"]["results"]] == ["High", "Mid", "Low"]


@pytest.mark.django_db
def test_an_unknown_ordering_falls_back_to_newest(api_client, make_product):
    make_product(name="First")
    make_product(name="Second")

    rows = api_client.get(reverse(PRODUCTS_URL), {"ordering": "nonsense"}).data["data"]["results"]

    assert [row["name"] for row in rows] == ["Second", "First"]


@pytest.mark.django_db
def test_market_and_day_filters_use_active_slots(
    api_client, product, seller_market, make_product, other_category
):
    from markets.models import Market

    quiet = Market.objects.create(
        name="Quiet Market",
        address="2 Nowhere Lane",
        latitude="10.5",
        longitude="106.5",
        open_time="06:00",
        close_time="10:00",
    )

    assert api_client.get(reverse(PRODUCTS_URL), {"market_id": seller_market.id}).data["data"][
        "count"
    ] == 1
    assert api_client.get(reverse(PRODUCTS_URL), {"market_id": quiet.id}).data["data"]["count"] == 0
    # Day 1 has an active slot; day 3's slot is switched off.
    assert api_client.get(reverse(PRODUCTS_URL), {"day": "1"}).data["data"]["count"] == 1
    assert api_client.get(reverse(PRODUCTS_URL), {"day": "3"}).data["data"]["count"] == 0


@pytest.mark.django_db
def test_the_detail_adds_description_and_markets(api_client, product, seller_market):
    product.description = "Ripe and local."
    product.save(update_fields=["description"])

    data = api_client.get(reverse(PRODUCT_URL, args=[product.id])).data["data"]

    assert data["description"] == "Ripe and local."
    assert data["markets"] == [
        {"market_id": seller_market.id, "market_name": "Central Market", "days": [1]}
    ]


@pytest.mark.django_db
def test_a_sold_out_product_still_has_a_detail_page(api_client, product):
    product.stock_quantity = 0
    product.save(update_fields=["stock_quantity"])

    response = api_client.get(reverse(PRODUCT_URL, args=[product.id]))

    assert response.status_code == 200
    assert response.data["data"]["availability"] == "OUT_OF_STOCK"


@pytest.mark.django_db
def test_is_favorite_is_filled_in_for_a_signed_in_customer(
    api_client, customer_user, product, make_product
):
    other = make_product(name="Not a favorite")
    FavoriteProduct.objects.create(customer=customer_user, product=product)
    api_client.force_authenticate(user=customer_user)

    rows = {r["name"]: r for r in api_client.get(reverse(PRODUCTS_URL)).data["data"]["results"]}

    assert rows["Tomato"]["is_favorite"] is True
    assert rows[other.name]["is_favorite"] is False


@pytest.mark.django_db
def test_an_admin_is_not_treated_as_a_customer_for_favorites(api_client, admin_user, product):
    api_client.force_authenticate(user=admin_user)

    row = api_client.get(reverse(PRODUCTS_URL)).data["data"]["results"][0]

    assert row["is_favorite"] is None
