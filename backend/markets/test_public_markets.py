from datetime import time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from favorites.models import FavoriteMarket
from markets.conftest import MONDAY, SATURDAY, WEDNESDAY
from markets.models import Market, MarketClosure, MarketOperatingDay

LIST_URL = "public-market-list"
DETAIL_URL = "public-market-detail"
FARMERS_URL = "public-market-farmer-list"

HCMC = ("10.762622", "106.660172")
NEARBY = ("10.800000", "106.700000")


@pytest.fixture
def far_market(db):
    market = Market.objects.create(
        name="Riverside Market",
        address="88 Riverside Road",
        latitude=NEARBY[0],
        longitude=NEARBY[1],
        open_time=time(7, 0),
        close_time=time(13, 0),
    )
    MarketOperatingDay.objects.create(market=market, day_of_week=SATURDAY)
    return market


@pytest.mark.django_db
def test_a_guest_can_list_markets(api_client, market):
    response = api_client.get(reverse(LIST_URL))

    assert response.status_code == 200
    row = response.data["data"]["results"][0]
    assert row["name"] == "Central Market"
    assert row["operating_days"] == [MONDAY, WEDNESDAY]
    assert row["open_time"] == "06:00"
    assert row["distance_km"] is None
    assert row["is_favorite"] is None


@pytest.mark.django_db
def test_deactivated_markets_are_hidden_from_the_public(api_client, market):
    market.is_active = False
    market.save(update_fields=["is_active"])

    assert api_client.get(reverse(LIST_URL)).data["data"]["count"] == 0
    assert api_client.get(reverse(DETAIL_URL, args=[market.id])).status_code == 404


@pytest.mark.django_db
def test_search_and_day_filters(api_client, market, far_market):
    assert api_client.get(reverse(LIST_URL), {"q": "riverside"}).data["data"]["count"] == 1
    assert api_client.get(reverse(LIST_URL), {"day": MONDAY}).data["data"]["count"] == 1
    assert api_client.get(reverse(LIST_URL), {"day": SATURDAY}).data["data"]["count"] == 1
    assert api_client.get(reverse(LIST_URL), {"day": "99"}).data["data"]["count"] == 2


@pytest.mark.django_db
def test_distance_is_measured_from_the_given_point(api_client, market, far_market):
    lat, lng = HCMC

    rows = api_client.get(reverse(LIST_URL), {"lat": lat, "lng": lng}).data["data"]["results"]

    by_name = {row["name"]: row for row in rows}
    assert by_name["Central Market"]["distance_km"] == 0.0
    assert 5.0 < by_name["Riverside Market"]["distance_km"] < 7.0


@pytest.mark.django_db
def test_ordering_by_distance(api_client, market, far_market):
    lat, lng = HCMC

    nearest_first = api_client.get(
        reverse(LIST_URL), {"lat": lat, "lng": lng, "ordering": "distance"}
    ).data["data"]["results"]
    assert [row["name"] for row in nearest_first] == ["Central Market", "Riverside Market"]

    by_name = api_client.get(reverse(LIST_URL), {"ordering": "distance"}).data["data"]["results"]
    assert [row["name"] for row in by_name] == ["Central Market", "Riverside Market"]


@pytest.mark.django_db
def test_upcoming_closures_respect_the_booking_horizon(api_client, market):
    today = timezone.localdate()
    soon = MarketClosure.objects.create(
        market=market,
        start_date=today + timedelta(days=2),
        end_date=today + timedelta(days=3),
        reason="Lunar New Year closure",
    )
    MarketClosure.objects.create(
        market=market, start_date=today + timedelta(days=40), end_date=today + timedelta(days=41)
    )

    row = api_client.get(reverse(DETAIL_URL, args=[market.id])).data["data"]

    assert [c["id"] for c in row["upcoming_closures"]] == [soon.id]
    assert row["upcoming_closures"][0]["reason"] == "Lunar New Year closure"


@pytest.mark.django_db
def test_the_detail_adds_description_and_map_provider(api_client, market):
    market.description = "The oldest market in town."
    market.save(update_fields=["description"])

    data = api_client.get(reverse(DETAIL_URL, args=[market.id])).data["data"]

    assert data["description"] == "The oldest market in town."
    assert data["map_provider"] == "OSM"


@pytest.mark.django_db
def test_is_favorite_is_filled_in_for_a_signed_in_customer(
    api_client, customer_user, market, far_market
):
    FavoriteMarket.objects.create(customer=customer_user, market=market)
    api_client.force_authenticate(user=customer_user)

    rows = {row["name"]: row for row in api_client.get(reverse(LIST_URL)).data["data"]["results"]}

    assert rows["Central Market"]["is_favorite"] is True
    assert rows["Riverside Market"]["is_favorite"] is False


@pytest.mark.django_db
def test_market_farmers_shows_only_approved_sellers(api_client, market, farmer_market):
    rows = api_client.get(reverse(FARMERS_URL, args=[market.id])).data["data"]["results"]

    assert len(rows) == 1
    assert rows[0]["stall_name"] == "Test Stall"
    assert rows[0]["markets"] == [
        {"market_id": market.id, "market_name": "Central Market", "stall_label": "Row B, Stall 12"}
    ]


@pytest.mark.django_db
def test_a_pending_farmer_is_not_listed_publicly(api_client, market, farmer_market, approved_farmer):
    approved_farmer.status = "PENDING"
    approved_farmer.save(update_fields=["status"])

    assert api_client.get(reverse(FARMERS_URL, args=[market.id])).data["data"]["count"] == 0


@pytest.mark.django_db
def test_farmers_of_an_unknown_market_are_a_404(api_client):
    assert api_client.get(reverse(FARMERS_URL, args=[9999])).status_code == 404
