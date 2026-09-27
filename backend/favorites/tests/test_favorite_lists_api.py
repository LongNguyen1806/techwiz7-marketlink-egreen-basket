import pytest
from rest_framework.test import APIClient

from accounts.auth.tokens import issue_tokens
from accounts.models import FarmerStatus
from favorites.models import FavoriteFarmer, FavoriteMarket, FavoriteProduct
from tests_support.factories import make_customer, make_farmer, make_market, make_product

FARMER_KEYS = {
    "id", "stall_name", "image", "rating_avg", "rating_count", "markets", "operating_days",
    "in_stock_product_count", "upcoming_closures", "distance_km", "is_favorite",
}
PRODUCT_KEYS = {
    "id", "name", "image", "price", "unit", "stock_quantity", "min_per_order", "max_per_order", "is_available", "availability",
    "category", "farmer", "rating_avg", "rating_count", "is_favorite",
}
MARKET_KEYS = {
    "id", "name", "address", "image", "latitude", "longitude", "operating_days", "open_time",
    "close_time", "upcoming_closures", "farmer_count", "distance_km", "is_favorite",
}


def _client(user) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
    return client


def _results(response) -> list:
    assert response.status_code == 200, response.json()
    return response.json()["data"]["results"]


@pytest.fixture
def customer(db):
    return make_customer()


@pytest.fixture
def api(customer):
    return _client(customer)


@pytest.mark.django_db
class TestFavoriteFarmerList:
    URL = "/api/customer/favorite-farmers/"

    def test_lists_own_favorite_farmers_as_summaries(self, api, customer):
        farmer = make_farmer()
        make_product(farmer=farmer, stock=4)
        FavoriteFarmer.objects.create(customer=customer, farmer=farmer)
        FavoriteFarmer.objects.create(customer=make_customer(), farmer=make_farmer())

        results = _results(api.get(self.URL))

        assert [row["id"] for row in results] == [farmer.pk]
        assert set(results[0]) == FARMER_KEYS
        assert (results[0]["stall_name"], results[0]["is_favorite"]) == (farmer.stall_name, True)
        assert results[0]["in_stock_product_count"] == 1
        assert api.get(self.URL).json()["data"]["count"] == 1

    @pytest.mark.parametrize("status", [FarmerStatus.PENDING, FarmerStatus.SUSPENDED, FarmerStatus.REJECTED])
    def test_a_farmer_who_is_no_longer_public_drops_out(self, api, customer, status):
        farmer = make_farmer(status=status)
        FavoriteFarmer.objects.create(customer=customer, farmer=farmer)

        assert _results(api.get(self.URL)) == []

    def test_empty_when_nothing_is_hearted(self, api):
        assert _results(api.get(self.URL)) == []

    def test_farmer_is_forbidden(self):
        assert _client(make_farmer().user).get(self.URL).status_code == 403

    def test_requires_login(self):
        assert APIClient().get(self.URL).status_code == 401


@pytest.mark.django_db
class TestFavoriteProductList:
    URL = "/api/customer/favorite-products/"

    def test_lists_own_favorite_products_as_cards(self, api, customer):
        product = make_product(farmer=make_farmer(), stock=7, price="2.50")
        FavoriteProduct.objects.create(customer=customer, product=product)
        FavoriteProduct.objects.create(customer=make_customer(), product=make_product(farmer=make_farmer()))

        results = _results(api.get(self.URL))

        assert [row["id"] for row in results] == [product.pk]
        assert set(results[0]) == PRODUCT_KEYS
        assert (results[0]["price"], results[0]["availability"], results[0]["is_favorite"]) == (
            "2.50", "IN_STOCK", True
        )

    def test_a_sold_out_product_stays_listed_for_the_restock_label(self, api, customer):
        # C-08 shows "Notify when back in stock" on these rows, so they must not be filtered out.
        product = make_product(farmer=make_farmer(), stock=0)
        FavoriteProduct.objects.create(customer=customer, product=product)

        [row] = _results(api.get(self.URL))

        assert (row["id"], row["availability"]) == (product.pk, "OUT_OF_STOCK")

    @pytest.mark.parametrize("overrides", [{"is_archived": True}, {"is_hidden_by_admin": True}])
    def test_a_product_that_is_no_longer_public_drops_out(self, api, customer, overrides):
        product = make_product(farmer=make_farmer(), **overrides)
        FavoriteProduct.objects.create(customer=customer, product=product)

        assert _results(api.get(self.URL)) == []

    def test_a_product_of_a_suspended_farmer_drops_out(self, api, customer):
        product = make_product(farmer=make_farmer(status=FarmerStatus.SUSPENDED))
        FavoriteProduct.objects.create(customer=customer, product=product)

        assert _results(api.get(self.URL)) == []

    def test_farmer_is_forbidden(self):
        assert _client(make_farmer().user).get(self.URL).status_code == 403


@pytest.mark.django_db
class TestFavoriteMarketList:
    URL = "/api/customer/favorite-markets/"

    def test_lists_own_favorite_markets_as_summaries(self, api, customer):
        market = make_market(days=[2, 4])
        FavoriteMarket.objects.create(customer=customer, market=market)
        FavoriteMarket.objects.create(customer=make_customer(), market=make_market())

        results = _results(api.get(self.URL))

        assert [row["id"] for row in results] == [market.pk]
        assert set(results[0]) == MARKET_KEYS
        assert (results[0]["operating_days"], results[0]["is_favorite"]) == ([2, 4], True)

    def test_an_inactive_market_drops_out(self, api, customer):
        market = make_market(is_active=False)
        FavoriteMarket.objects.create(customer=customer, market=market)

        assert _results(api.get(self.URL)) == []

    def test_farmer_is_forbidden(self):
        assert _client(make_farmer().user).get(self.URL).status_code == 403


@pytest.mark.django_db
class TestFavoriteListQueryCount:
    def test_query_count_does_not_grow_with_the_number_of_rows(self, api, customer, django_assert_max_num_queries):
        for _ in range(5):
            farmer = make_farmer()
            make_product(farmer=farmer)
            FavoriteFarmer.objects.create(customer=customer, farmer=farmer)

        with django_assert_max_num_queries(12):
            assert len(_results(api.get("/api/customer/favorite-farmers/"))) == 5
