from datetime import time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import FarmerStatus
from catalog.models import Category, Product, ReviewStatus, Unit
from favorites.models import FavoriteFarmer
from markets.models import FarmerClosure, FarmerMarket, FarmerMarketStatus, Market, PickupSlot

LIST_URL = "public-farmer-list"
DETAIL_URL = "public-farmer-detail"


@pytest.fixture
def make_completed_order(market, customer_user, category):
    """A completed order, optionally with a stall review, for testing the ranking."""
    from datetime import datetime, time, timedelta

    from django.utils import timezone

    from catalog.models import Product, Unit
    from orders.models import Order, OrderItem, OrderStatus
    from reviews.models import FarmerReview

    def _make(*, farmer, with_review=False):
        pickup_date = timezone.localdate() - timedelta(days=1)
        start = timezone.make_aware(datetime.combine(pickup_date, time(8, 0)))
        order = Order.objects.create(
            customer=customer_user, farmer=farmer, market=market,
            pickup_date=pickup_date, pickup_start_at=start,
            pickup_end_at=start + timedelta(hours=2), cutoff_at=start - timedelta(hours=12),
            status=OrderStatus.COMPLETED, total_amount="5.00",
        )
        product = Product.objects.create(
            review_status=ReviewStatus.APPROVED,
            farmer=farmer, category=category, name=f"Produce {order.pk}",
            price="2.50", unit=Unit.KG, stock_quantity=5,
        )
        OrderItem.objects.create(
            order=order, product=product, product_name=product.name,
            unit_price=product.price, unit=product.unit, quantity=2, line_total="5.00",
        )
        if with_review:
            FarmerReview.objects.create(order=order, rating=5, comment="Good stall.")
        return order

    return _make

@pytest.fixture
def market(db):
    return Market.objects.create(
        name="Central Market",
        address="1 Market Street",
        latitude="10.762622",
        longitude="106.660172",
        open_time=time(6, 0),
        close_time=time(12, 0),
    )


@pytest.fixture
def approved_farmer(farmer_user):
    profile = farmer_user.farmer_profile
    profile.status = FarmerStatus.APPROVED
    profile.latitude = "10.800000"
    profile.longitude = "106.700000"
    profile.operating_days = [1, 3]
    profile.save(
        update_fields=["status", "latitude", "longitude", "operating_days"]
    )
    return profile


@pytest.fixture
def stall(market, approved_farmer):
    farmer_market = FarmerMarket.objects.create(
        farmer=approved_farmer, market=market, stall_label="Row B, Stall 12"
    )
    PickupSlot.objects.create(
        farmer_market=farmer_market, day_of_week=1, start_time=time(7, 0), end_time=time(9, 0)
    )
    PickupSlot.objects.create(
        farmer_market=farmer_market,
        day_of_week=3,
        start_time=time(7, 0),
        end_time=time(9, 0),
        is_active=False,
    )
    return farmer_market


@pytest.fixture
def category(db):
    return Category.objects.create(name="Vegetables", display_order=1)


@pytest.mark.django_db
def test_a_guest_can_list_approved_farmers(api_client, approved_farmer, stall):
    response = api_client.get(reverse(LIST_URL))

    assert response.status_code == 200
    row = response.data["data"]["results"][0]
    assert row["id"] == approved_farmer.user_id
    assert row["stall_name"] == "Test Stall"
    assert row["rating_avg"] is None
    assert row["rating_count"] == 0
    assert row["in_stock_product_count"] == 0
    assert row["is_favorite"] is None


@pytest.mark.django_db
def test_only_approved_and_enabled_farmers_are_public(api_client, approved_farmer):
    approved_farmer.status = FarmerStatus.PENDING
    approved_farmer.save(update_fields=["status"])
    assert api_client.get(reverse(LIST_URL)).data["data"]["count"] == 0
    assert api_client.get(reverse(DETAIL_URL, args=[approved_farmer.user_id])).status_code == 404

    approved_farmer.status = FarmerStatus.APPROVED
    approved_farmer.save(update_fields=["status"])
    user = approved_farmer.user
    user.is_active = False
    user.save(update_fields=["is_active"])
    assert api_client.get(reverse(LIST_URL)).data["data"]["count"] == 0


@pytest.mark.django_db
def test_operating_days_come_from_the_profile(api_client, approved_farmer, stall):
    row = api_client.get(reverse(LIST_URL)).data["data"]["results"][0]

    assert row["operating_days"] == [1, 3]
    assert row["markets"] == [
        {
            "market_id": stall.market_id,
            "market_name": "Central Market",
            "stall_label": "Row B, Stall 12",
        }
    ]


@pytest.mark.django_db
def test_in_stock_count_ignores_hidden_and_sold_out_products(
    api_client, approved_farmer, stall, category
):
    Product.objects.create(
        review_status=ReviewStatus.APPROVED,
        farmer=approved_farmer, category=category, name="In stock", price="2.00",
        unit=Unit.KG, stock_quantity=4,
    )
    Product.objects.create(
        review_status=ReviewStatus.APPROVED,
        farmer=approved_farmer, category=category, name="Sold out", price="2.00",
        unit=Unit.KG, stock_quantity=0,
    )
    Product.objects.create(
        review_status=ReviewStatus.APPROVED,
        farmer=approved_farmer, category=category, name="Hidden", price="2.00",
        unit=Unit.KG, stock_quantity=4, is_hidden_by_admin=True,
    )

    row = api_client.get(reverse(LIST_URL)).data["data"]["results"][0]

    assert row["in_stock_product_count"] == 1


@pytest.mark.django_db
def test_the_rating_average_survives_the_product_count(
    api_client, approved_farmer, stall, category, market
):
    from datetime import datetime

    from orders.models import Order, OrderStatus
    from reviews.models import FarmerReview

    for index in range(3):
        Product.objects.create(
            review_status=ReviewStatus.APPROVED,
            farmer=approved_farmer, category=category, name=f"Product {index}",
            price="2.00", unit=Unit.KG, stock_quantity=4,
        )
    for rating in (4, 2):
        start = timezone.make_aware(datetime.combine(timezone.localdate(), time(8, 0)))
        order = Order.objects.create(
            customer=approved_farmer.user, farmer=approved_farmer, market=market,
            pickup_date=timezone.localdate(), pickup_start_at=start,
            pickup_end_at=start + timedelta(hours=2), cutoff_at=start - timedelta(hours=12),
            status=OrderStatus.COMPLETED, total_amount="5.00",
        )
        FarmerReview.objects.create(order=order, rating=rating)

    row = api_client.get(reverse(LIST_URL)).data["data"]["results"][0]

    assert row["in_stock_product_count"] == 3
    assert row["rating_count"] == 2
    assert row["rating_avg"] == 3.0


@pytest.mark.django_db
def test_upcoming_closures_respect_the_horizon(api_client, approved_farmer, stall):
    today = timezone.localdate()
    soon = FarmerClosure.objects.create(
        farmer=approved_farmer,
        start_date=today + timedelta(days=1),
        end_date=today + timedelta(days=2),
        reason="Harvest break",
    )
    FarmerClosure.objects.create(
        farmer=approved_farmer,
        start_date=today + timedelta(days=40),
        end_date=today + timedelta(days=41),
    )

    row = api_client.get(reverse(LIST_URL)).data["data"]["results"][0]

    assert [c["id"] for c in row["upcoming_closures"]] == [soon.id]
    assert row["upcoming_closures"][0]["reason"] == "Harvest break"


@pytest.mark.django_db
def test_distance_is_to_the_market_not_the_farm(api_client, approved_farmer, stall):
    response = api_client.get(
        reverse(LIST_URL), {"lat": "10.800000", "lng": "106.700000", "ordering": "distance"}
    )

    row = response.data["data"]["results"][0]
    assert 5.0 < row["distance_km"] < 7.0

    at_market = api_client.get(reverse(LIST_URL), {"lat": "10.762622", "lng": "106.660172"})
    assert at_market.data["data"]["results"][0]["distance_km"] == 0.0

    assert api_client.get(reverse(LIST_URL), {"ordering": "distance"}).status_code == 200


@pytest.mark.django_db
def test_filters_by_market_day_and_category(api_client, approved_farmer, stall, category):
    Product.objects.create(
        review_status=ReviewStatus.APPROVED,
        farmer=approved_farmer, category=category, name="Tomato", price="2.00",
        unit=Unit.KG, stock_quantity=4,
    )

    assert api_client.get(reverse(LIST_URL), {"market_id": stall.market_id}).data["data"]["count"] == 1
    assert api_client.get(reverse(LIST_URL), {"market_id": "9999"}).data["data"]["count"] == 0
    assert api_client.get(reverse(LIST_URL), {"day": "1"}).data["data"]["count"] == 1
    assert api_client.get(reverse(LIST_URL), {"day": "3"}).data["data"]["count"] == 0
    assert api_client.get(reverse(LIST_URL), {"day": "5"}).data["data"]["count"] == 0
    assert api_client.get(reverse(LIST_URL), {"category_id": category.id}).data["data"]["count"] == 1
    assert api_client.get(reverse(LIST_URL), {"category_id": "9999"}).data["data"]["count"] == 0


@pytest.mark.django_db
def test_search_matches_stall_or_market_name_but_not_the_farm_address(
    api_client, approved_farmer, stall
):
    assert api_client.get(reverse(LIST_URL), {"q": "test stall"}).data["data"]["count"] == 1
    assert api_client.get(reverse(LIST_URL), {"q": "central market"}).data["data"]["count"] == 1
    assert api_client.get(reverse(LIST_URL), {"q": "34 Market Street"}).data["data"]["count"] == 0
    assert api_client.get(reverse(LIST_URL), {"q": "nowhere"}).data["data"]["count"] == 0


@pytest.mark.django_db
def test_the_detail_adds_contact_details_and_pickup_windows(api_client, approved_farmer, stall):
    data = api_client.get(reverse(DETAIL_URL, args=[approved_farmer.user_id])).data["data"]

    assert data["contact_person"] == "Test Farmer"
    assert data["phone"] == "0907654321"
    assert data["order_cutoff_hours"] == 12
    assert "address" not in data
    assert "latitude" not in data
    assert "longitude" not in data
    assert len(data["pickup_windows"]) == 1
    window = data["pickup_windows"][0]
    assert window["market_name"] == "Central Market"
    assert window["stall_label"] == "Row B, Stall 12"
    assert [slot["day_of_week"] for slot in window["slots"]] == [1]
    assert window["slots"][0]["start_time"] == "07:00"


@pytest.mark.django_db
def test_pickup_windows_skip_deactivated_markets(api_client, approved_farmer, stall, market):
    other = Market.objects.create(
        name="Riverside Market",
        address="88 Riverside Road",
        latitude="10.800000",
        longitude="106.700000",
        open_time=time(6, 0),
        close_time=time(12, 0),
    )
    FarmerMarket.objects.create(farmer=approved_farmer, market=other, stall_label="Gate 2")
    market.is_active = False
    market.save(update_fields=["is_active"])

    data = api_client.get(reverse(DETAIL_URL, args=[approved_farmer.user_id])).data["data"]

    assert [window["market_name"] for window in data["pickup_windows"]] == ["Riverside Market"]
    assert [row["market_name"] for row in data["markets"]] == ["Riverside Market"]


@pytest.mark.django_db
def test_a_stall_whose_only_market_closed_is_no_longer_public(
    api_client, approved_farmer, stall, market
):
    market.is_active = False
    market.save(update_fields=["is_active"])

    assert api_client.get(reverse(LIST_URL)).data["data"]["count"] == 0
    assert api_client.get(reverse(DETAIL_URL, args=[approved_farmer.user_id])).status_code == 404


@pytest.mark.django_db
def test_a_stall_waiting_for_its_first_market_is_not_public(api_client, approved_farmer, market):
    FarmerMarket.objects.create(
        farmer=approved_farmer,
        market=market,
        stall_label="Row B, Stall 12",
        status=FarmerMarketStatus.PENDING,
    )

    assert api_client.get(reverse(LIST_URL)).data["data"]["count"] == 0
    assert api_client.get(reverse(LIST_URL), {"q": "central market"}).data["data"]["count"] == 0
    assert api_client.get(reverse(DETAIL_URL, args=[approved_farmer.user_id])).status_code == 404


@pytest.mark.django_db
def test_a_pending_second_market_stays_out_of_the_public_profile(
    api_client, approved_farmer, stall
):
    other = Market.objects.create(
        name="Riverside Market",
        address="88 Riverside Road",
        latitude="10.800000",
        longitude="106.700000",
        open_time=time(6, 0),
        close_time=time(12, 0),
    )
    FarmerMarket.objects.create(
        farmer=approved_farmer, market=other, stall_label="Gate 2", status=FarmerMarketStatus.PENDING
    )

    data = api_client.get(reverse(DETAIL_URL, args=[approved_farmer.user_id])).data["data"]

    assert [row["market_name"] for row in data["markets"]] == ["Central Market"]
    assert api_client.get(reverse(LIST_URL), {"market_id": other.id}).data["data"]["count"] == 0


@pytest.mark.django_db
def test_a_stall_at_two_markets_is_listed_once_by_its_nearest_market(
    api_client, approved_farmer, stall
):
    far = Market.objects.create(
        name="Far Market",
        address="200 Far Road",
        latitude="11.500000",
        longitude="107.500000",
        open_time=time(6, 0),
        close_time=time(12, 0),
    )
    FarmerMarket.objects.create(farmer=approved_farmer, market=far, stall_label="Far row")

    results = api_client.get(
        reverse(LIST_URL), {"lat": "10.762622", "lng": "106.660172", "ordering": "distance"}
    ).data["data"]["results"]

    assert [row["id"] for row in results] == [approved_farmer.user_id]
    assert results[0]["distance_km"] == 0.0


@pytest.mark.django_db
def test_is_favorite_is_filled_in_for_a_signed_in_customer(
    api_client, customer_user, approved_farmer, stall
):
    FavoriteFarmer.objects.create(customer=customer_user, farmer=approved_farmer)
    api_client.force_authenticate(user=customer_user)

    row = api_client.get(reverse(LIST_URL)).data["data"]["results"][0]

    assert row["is_favorite"] is True


@pytest.mark.django_db
def test_an_unknown_farmer_is_a_404(api_client):
    assert api_client.get(reverse(DETAIL_URL, args=[9999])).status_code == 404




@pytest.mark.django_db
def test_the_busiest_stall_comes_first_by_default(
    api_client, approved_farmer, stall, make_farmer, market, make_completed_order
):
    quiet = make_farmer(email="quiet@marketlink.test", stall_name="Quiet Stall")
    quiet.status = FarmerStatus.APPROVED
    quiet.save(update_fields=["status"])
    FarmerMarket.objects.create(farmer=quiet, market=market, stall_label="Row Q")
    for _ in range(3):
        make_completed_order(farmer=approved_farmer)

    response = api_client.get(reverse("public-farmer-list"))

    names = [row["stall_name"] for row in response.data["data"]["results"]]
    assert names[0] == approved_farmer.stall_name
    assert quiet.stall_name in names


@pytest.mark.django_db
def test_a_sale_counts_double_a_review(
    api_client, approved_farmer, stall, market, make_farmer, make_completed_order
):
    make_completed_order(farmer=approved_farmer)
    make_completed_order(farmer=approved_farmer)

    smaller = make_farmer(email="small@marketlink.test", stall_name="Small Stall")
    smaller.status = FarmerStatus.APPROVED
    smaller.save(update_fields=["status"])
    FarmerMarket.objects.create(farmer=smaller, market=market, stall_label="Row S")
    make_completed_order(farmer=smaller, with_review=True)

    names = [
        row["stall_name"]
        for row in api_client.get(reverse("public-farmer-list")).data["data"]["results"]
    ]
    assert names.index(approved_farmer.stall_name) < names.index("Small Stall")


@pytest.mark.django_db
def test_enough_reviews_can_overturn_a_one_sale_lead(
    api_client, approved_farmer, stall, market, make_farmer, make_completed_order
):
    for _ in range(4):
        make_completed_order(farmer=approved_farmer)

    talked_about = make_farmer(email="talked@marketlink.test", stall_name="Talked About")
    talked_about.status = FarmerStatus.APPROVED
    talked_about.save(update_fields=["status"])
    FarmerMarket.objects.create(farmer=talked_about, market=market, stall_label="Row T")
    for _ in range(3):
        make_completed_order(farmer=talked_about, with_review=True)

    names = [
        row["stall_name"]
        for row in api_client.get(reverse("public-farmer-list")).data["data"]["results"]
    ]
    assert names.index("Talked About") < names.index(approved_farmer.stall_name)


@pytest.mark.django_db
def test_an_explicit_sort_still_wins(api_client, approved_farmer, make_farmer):
    make_farmer(email="aaa@marketlink.test", stall_name="Aardvark Stall").__class__.objects.filter(
        stall_name="Aardvark Stall"
    ).update(status=FarmerStatus.APPROVED)

    names = [
        row["stall_name"]
        for row in api_client.get(
            reverse("public-farmer-list"), {"ordering": "name"}
        ).data["data"]["results"]
    ]
    assert names == sorted(names)


GEOCODE_URL = "public-geocode"
GEOCODE = "accounts.public_portal.views_public.geocode_address"


@pytest.mark.django_db
def test_geocode_returns_the_point_for_an_address(api_client):
    from decimal import Decimal
    from unittest import mock

    with mock.patch(GEOCODE, return_value=(Decimal("10.790451"), Decimal("106.688785"))) as geocode:
        response = api_client.get(reverse(GEOCODE_URL), {"q": "Cho Tan Dinh, Ho Chi Minh City"})

    assert response.status_code == 200
    assert response.data["data"] == {"found": True, "latitude": 10.790451, "longitude": 106.688785}
    geocode.assert_called_once_with("Cho Tan Dinh, Ho Chi Minh City")


@pytest.mark.django_db
def test_geocode_says_not_found_instead_of_failing(api_client):
    from unittest import mock

    with mock.patch(GEOCODE, return_value=None):
        response = api_client.get(reverse(GEOCODE_URL), {"q": "somewhere unknown"})

    assert response.status_code == 200
    assert response.data["data"] == {"found": False, "latitude": None, "longitude": None}


@pytest.mark.django_db
def test_geocode_rejects_a_query_too_short_to_search(api_client):
    from unittest import mock

    with mock.patch(GEOCODE) as geocode:
        response = api_client.get(reverse(GEOCODE_URL), {"q": "abc"})

    assert response.status_code == 400
    geocode.assert_not_called()
