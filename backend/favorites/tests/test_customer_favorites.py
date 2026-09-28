from unittest import mock

import pytest
from rest_framework.test import APIClient

from accounts.auth.tokens import issue_tokens
from accounts.models import FarmerStatus
from favorites.models import FavoriteFarmer, FavoriteMarket, FavoriteProduct
from tests_support.factories import make_customer, make_farmer, make_market, make_product

IDS_URL = "/api/customer/favorite-ids/"


def _client(user) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
    return client


@pytest.fixture
def customer(db):
    return make_customer()


@pytest.fixture
def api(customer):
    return _client(customer)


KINDS = [
    ("farmers", "farmer_id", FavoriteFarmer, lambda: make_farmer()),
    ("products", "product_id", FavoriteProduct, lambda: make_product(farmer=make_farmer())),
    ("markets", "market_id", FavoriteMarket, lambda: make_market()),
]


@pytest.mark.django_db
@pytest.mark.parametrize("kind, field, model, make_target", KINDS)
class TestAddAndRemove:
    def test_add_returns_201_with_the_id(self, api, customer, kind, field, model, make_target):
        target = make_target()

        response = api.post(f"/api/customer/favorite-{kind}/", {field: target.pk}, format="json")

        assert response.status_code == 201
        assert response.json()["data"] == {field: target.pk}
        assert model.objects.filter(customer=customer).count() == 1

    def test_adding_twice_is_still_201_without_a_duplicate(self, api, customer, kind, field, model, make_target):
        target = make_target()
        api.post(f"/api/customer/favorite-{kind}/", {field: target.pk}, format="json")

        response = api.post(f"/api/customer/favorite-{kind}/", {field: target.pk}, format="json")

        assert response.status_code == 201
        assert model.objects.filter(customer=customer).count() == 1

    def test_unknown_id_is_not_found(self, api, kind, field, model, make_target):
        response = api.post(f"/api/customer/favorite-{kind}/", {field: 999999}, format="json")

        assert response.status_code == 404

    def test_missing_id_is_a_validation_error(self, api, kind, field, model, make_target):
        response = api.post(f"/api/customer/favorite-{kind}/", {}, format="json")

        assert (response.status_code, response.json()["code"]) == (400, "VALIDATION_ERROR")
        assert field in response.json()["errors"]

    def test_remove_returns_204(self, api, customer, kind, field, model, make_target):
        target = make_target()
        api.post(f"/api/customer/favorite-{kind}/", {field: target.pk}, format="json")

        response = api.delete(f"/api/customer/favorite-{kind}/{target.pk}/")

        assert response.status_code == 204
        assert not model.objects.filter(customer=customer).exists()

    def test_removing_something_not_favorited_is_still_204(self, api, kind, field, model, make_target):
        assert api.delete(f"/api/customer/favorite-{kind}/{make_target().pk}/").status_code == 204

    def test_removing_only_touches_your_own_favorites(self, api, kind, field, model, make_target):
        target = make_target()
        other = make_customer()
        _client(other).post(f"/api/customer/favorite-{kind}/", {field: target.pk}, format="json")

        api.delete(f"/api/customer/favorite-{kind}/{target.pk}/")

        assert model.objects.filter(customer=other).count() == 1

    def test_farmer_is_forbidden(self, kind, field, model, make_target):
        farmer_client = _client(make_farmer().user)

        assert farmer_client.post(f"/api/customer/favorite-{kind}/", {field: 1}, format="json").status_code == 403

    def test_requires_login(self, kind, field, model, make_target):
        assert APIClient().post(f"/api/customer/favorite-{kind}/", {field: 1}, format="json").status_code == 401


@pytest.mark.django_db
class TestOnlyPublicTargets:
    @pytest.mark.parametrize("status", [FarmerStatus.PENDING, FarmerStatus.SUSPENDED, FarmerStatus.REJECTED])
    def test_farmer_must_be_approved(self, api, status):
        farmer = make_farmer(status=status)

        assert api.post("/api/customer/favorite-farmers/", {"farmer_id": farmer.pk}, format="json").status_code == 404

    @pytest.mark.parametrize("overrides", [{"is_archived": True}, {"is_hidden_by_admin": True}])
    def test_archived_or_hidden_product_cannot_be_favorited(self, api, overrides):
        product = make_product(farmer=make_farmer(), **overrides)

        assert api.post("/api/customer/favorite-products/", {"product_id": product.pk}, format="json").status_code == 404

    def test_product_of_a_suspended_farmer_cannot_be_favorited(self, api):
        product = make_product(farmer=make_farmer(status=FarmerStatus.SUSPENDED))

        assert api.post("/api/customer/favorite-products/", {"product_id": product.pk}, format="json").status_code == 404

    def test_out_of_stock_product_can_be_favorited_for_restock_alerts(self, api):
        product = make_product(farmer=make_farmer(), stock=0)

        assert api.post("/api/customer/favorite-products/", {"product_id": product.pk}, format="json").status_code == 201

    def test_inactive_market_cannot_be_favorited(self, api):
        market = make_market(is_active=False)

        assert api.post("/api/customer/favorite-markets/", {"market_id": market.pk}, format="json").status_code == 404


@pytest.mark.django_db
class TestConcurrentAdd:
    def test_losing_the_race_to_the_unique_index_is_still_201(self, api, customer):
        product = make_product(farmer=make_farmer())
        api.post("/api/customer/favorite-products/", {"product_id": product.pk}, format="json")

        with mock.patch("favorites.services.favorite_service._already_saved", return_value=False):
            response = api.post("/api/customer/favorite-products/", {"product_id": product.pk}, format="json")

        assert response.status_code == 201
        assert FavoriteProduct.objects.filter(customer=customer).count() == 1


@pytest.mark.django_db
class TestFavoriteIds:
    def test_lists_own_ids_per_kind(self, api, customer):
        farmer, market = make_farmer(), make_market()
        product = make_product(farmer=farmer)
        api.post("/api/customer/favorite-farmers/", {"farmer_id": farmer.pk}, format="json")
        api.post("/api/customer/favorite-products/", {"product_id": product.pk}, format="json")
        api.post("/api/customer/favorite-markets/", {"market_id": market.pk}, format="json")
        _client(make_customer()).post("/api/customer/favorite-markets/", {"market_id": make_market().pk}, format="json")

        response = api.get(IDS_URL)

        assert response.status_code == 200
        assert response.json()["data"] == {
            "farmer_ids": [farmer.pk], "product_ids": [product.pk], "market_ids": [market.pk],
        }

    def test_empty_for_a_new_customer(self, api):
        assert api.get(IDS_URL).json()["data"] == {"farmer_ids": [], "product_ids": [], "market_ids": []}

    def test_farmer_is_forbidden(self):
        assert _client(make_farmer().user).get(IDS_URL).status_code == 403
