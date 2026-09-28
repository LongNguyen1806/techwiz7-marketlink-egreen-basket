from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.auth.tokens import issue_tokens
from accounts.models import FarmerStatus
from favorites.models import FavoriteFarmer, FavoriteMarket
from notifications.models import Notification, NotificationType
from orders.models import OrderStatus
from reviews.models import FarmerReview, ProductReview
from tests_support.factories import make_customer, make_farmer, make_market, make_order, make_product

URL = "/api/customer/dashboard/"
DASHBOARD_KEYS = {
    "counts", "upcoming", "favorite_farmers", "favorite_markets", "last_order_id", "recent_notifications",
}
COUNT_KEYS = {"open", "ready_for_pickup", "completed", "pending_review"}


def _client(user) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
    return client


@pytest.fixture
def shop(db):
    customer = make_customer()
    farmer = make_farmer()
    return SimpleNamespace(
        customer=customer, api=_client(customer), farmer=farmer, market=make_market(),
        product=make_product(farmer=farmer, stock=10),
    )


def _order(shop, **kwargs):
    kwargs.setdefault("market", shop.market)
    return make_order(customer=shop.customer, product=shop.product, **kwargs)


def _data(shop) -> dict:
    response = shop.api.get(URL)
    assert response.status_code == 200, response.json()
    return response.json()["data"]


def _notify(user, **kwargs):
    return Notification.objects.create(
        recipient=user, type=NotificationType.ORDER_ACCEPTED, title="t", message="m", **kwargs
    )


@pytest.mark.django_db
class TestDashboardShape:
    def test_returns_every_block(self, shop):
        data = _data(shop)

        assert set(data) == DASHBOARD_KEYS
        assert set(data["counts"]) == COUNT_KEYS

    def test_a_brand_new_customer_sees_zeros_and_empty_lists(self, shop):
        data = _data(shop)

        assert data["counts"] == {"open": 0, "ready_for_pickup": 0, "completed": 0, "pending_review": 0}
        assert (data["upcoming"], data["favorite_farmers"]) == ([], [])
        assert (data["favorite_markets"], data["recent_notifications"]) == ([], [])
        assert data["last_order_id"] is None


@pytest.mark.django_db
class TestDashboardCounts:
    def test_counts_open_ready_and_completed(self, shop):
        for status in (OrderStatus.PLACED, OrderStatus.ACCEPTED, OrderStatus.READY_FOR_PICKUP):
            _order(shop, status=status)
        _order(shop, status=OrderStatus.COMPLETED)
        for status in (OrderStatus.CANCELLED, OrderStatus.DECLINED, OrderStatus.NO_SHOW, OrderStatus.EXPIRED):
            _order(shop, status=status)

        counts = _data(shop)["counts"]

        assert (counts["open"], counts["ready_for_pickup"], counts["completed"]) == (3, 1, 1)

    def test_only_counts_own_orders(self, shop):
        make_order(customer=make_customer(), product=shop.product, status=OrderStatus.COMPLETED)

        assert _data(shop)["counts"]["completed"] == 0

    def test_pending_review_drops_as_the_customer_reviews(self, shop):
        order = _order(shop, status=OrderStatus.COMPLETED)
        item = order.items.get()

        assert _data(shop)["counts"]["pending_review"] == 1
        FarmerReview.objects.create(order=order, rating=5)
        assert _data(shop)["counts"]["pending_review"] == 1
        ProductReview.objects.create(order_item=item, rating=4)
        assert _data(shop)["counts"]["pending_review"] == 0

    def test_only_completed_orders_can_be_pending_review(self, shop):
        _order(shop, status=OrderStatus.CANCELLED)

        assert _data(shop)["counts"]["pending_review"] == 0

    def test_overdue_orders_are_swept_before_counting(self, shop):
        overdue = _order(shop, pickup_start_at=timezone.now() - timedelta(hours=1))

        counts = _data(shop)["counts"]

        overdue.refresh_from_db()
        assert overdue.status == OrderStatus.EXPIRED
        assert counts["open"] == 0


@pytest.mark.django_db
class TestDashboardUpcoming:
    def test_at_most_three_nearest_pickups_first(self, shop):
        orders = [_order(shop, pickup_start_at=timezone.now() + timedelta(days=days)) for days in (5, 2, 4, 3)]

        upcoming = _data(shop)["upcoming"]

        assert [row["id"] for row in upcoming] == [orders[1].pk, orders[3].pk, orders[2].pk]
        assert "is_expiring_soon" in upcoming[0] and "farmer" in upcoming[0]

    def test_finished_and_overdue_orders_are_not_upcoming(self, shop):
        _order(shop, status=OrderStatus.COMPLETED, pickup_start_at=timezone.now() + timedelta(days=2))
        _order(shop, status=OrderStatus.ACCEPTED, pickup_start_at=timezone.now() - timedelta(hours=2))

        assert _data(shop)["upcoming"] == []


@pytest.mark.django_db
class TestDashboardShortcuts:
    def test_at_most_four_favorite_farmers(self, shop):
        farmers = [make_farmer() for _ in range(5)]
        for farmer in farmers:
            FavoriteFarmer.objects.create(customer=shop.customer, farmer=farmer)

        rows = _data(shop)["favorite_farmers"]

        assert len(rows) == 4
        assert {"stall_name", "rating_avg", "in_stock_product_count", "is_favorite"} <= set(rows[0])

    def test_a_farmer_who_is_no_longer_public_is_left_out(self, shop):
        FavoriteFarmer.objects.create(customer=shop.customer, farmer=make_farmer(status=FarmerStatus.SUSPENDED))

        assert _data(shop)["favorite_farmers"] == []

    def test_favorite_markets_use_the_market_summary(self, shop):
        FavoriteMarket.objects.create(customer=shop.customer, market=shop.market)
        FavoriteMarket.objects.create(customer=shop.customer, market=make_market(is_active=False))

        rows = _data(shop)["favorite_markets"]

        assert [row["id"] for row in rows] == [shop.market.pk]
        assert {"operating_days", "farmer_count", "latitude"} <= set(rows[0])

    def test_last_order_id_is_the_most_recent_order(self, shop):
        _order(shop, status=OrderStatus.COMPLETED)
        newest = _order(shop, status=OrderStatus.CANCELLED)

        assert _data(shop)["last_order_id"] == newest.pk


@pytest.mark.django_db
class TestDashboardNotifications:
    def test_at_most_five_newest_first_and_only_mine(self, shop):
        mine = [_notify(shop.customer) for _ in range(6)]
        _notify(make_customer())

        rows = _data(shop)["recent_notifications"]

        assert [row["id"] for row in rows] == [note.pk for note in reversed(mine[1:])]
        assert set(rows[0]) == {
            "id", "type", "title", "message", "target_url", "is_read", "read_at", "created_at"
        }


@pytest.mark.django_db
class TestDashboardAccess:
    def test_farmer_is_forbidden(self, shop):
        assert _client(shop.farmer.user).get(URL).status_code == 403

    def test_requires_login(self, shop):
        assert APIClient().get(URL).status_code == 401

    def test_query_count_does_not_grow_with_the_data(self, shop, django_assert_max_num_queries):
        for _ in range(4):
            _order(shop, status=OrderStatus.COMPLETED)
            _order(shop, pickup_start_at=timezone.now() + timedelta(days=3))
            FavoriteFarmer.objects.create(customer=shop.customer, farmer=make_farmer())
            _notify(shop.customer)

        with django_assert_max_num_queries(25):
            assert len(_data(shop)["upcoming"]) == 3
