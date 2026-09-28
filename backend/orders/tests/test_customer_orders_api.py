from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone
from rest_framework.test import APIClient

from accounts.auth.tokens import issue_tokens
from orders.models import ActorRole, ChangeReason, OrderStatusHistory, Transition
from orders.services.fsm import record_order_placed
from reviews.models import FarmerReview, ProductReview
from tests_support.factories import make_customer, make_farmer, make_order, make_product

LIST_URL = "/api/customer/orders/"
SUMMARY_KEYS = {
    "id", "status", "is_overdue", "is_expiring_soon", "has_pending_change", "needs_new_pickup", "version", "customer", "farmer", "market", "stall_label",
    "pickup_date", "pickup_start_at", "pickup_end_at", "cutoff_at", "item_count", "total_amount", "created_at",
}
DETAIL_KEYS = SUMMARY_KEYS | {
    "pickup_slot_id", "note", "items", "status_history", "pending_change", "allowed_actions", "review_state",
}
OPEN, HISTORY = ["PLACED", "ACCEPTED", "READY_FOR_PICKUP"], ["COMPLETED", "CANCELLED", "DECLINED", "NO_SHOW", "EXPIRED"]


def _client(user) -> APIClient:
    client = APIClient()
    client.credentials(HTTP_AUTHORIZATION=f"Bearer {issue_tokens(user)['access']}")
    return client


def _detail_url(order) -> str:
    return f"/api/customer/orders/{order.pk}/"


def _cancel(client, order, version=None, body=None, **headers):
    if version is not False:
        headers["HTTP_IF_MATCH"] = str(order.version if version is None else version)
    return client.post(f"/api/customer/orders/{order.pk}/cancel/", body or {}, format="json", **headers)


@pytest.fixture
def shop(db):
    farmer = make_farmer()
    customer = make_customer()
    return SimpleNamespace(
        customer=customer, api=_client(customer), farmer=farmer, product=make_product(farmer=farmer, stock=10)
    )


def _order(shop, **kwargs):
    return make_order(customer=shop.customer, product=shop.product, **kwargs)


def _results(response) -> list:
    assert response.status_code == 200
    return response.json()["data"]["results"]


@pytest.mark.django_db
class TestListOrders:
    def test_lists_only_own_orders_as_summaries(self, shop):
        mine = _order(shop)
        make_order(customer=make_customer(), product=shop.product)

        results = _results(shop.api.get(LIST_URL))

        assert [row["id"] for row in results] == [mine.pk]
        assert set(results[0]) == SUMMARY_KEYS
        assert results[0]["has_pending_change"] is False
        assert shop.api.get(LIST_URL).json()["data"]["count"] == 1

    def test_open_tab_and_history_tab(self, shop):
        by_status = {status: _order(shop, status=status) for status in OPEN + HISTORY}

        open_ids = {row["id"] for row in _results(shop.api.get(LIST_URL, {"tab": "open"}))}
        history_ids = {row["id"] for row in _results(shop.api.get(LIST_URL, {"tab": "history"}))}

        assert open_ids == {by_status[status].pk for status in OPEN}
        assert history_ids == {by_status[status].pk for status in HISTORY}

    def test_open_tab_shows_the_nearest_pickup_first(self, shop):
        later = _order(shop, pickup_start_at=timezone.now() + timedelta(days=4))
        sooner = _order(shop, pickup_start_at=timezone.now() + timedelta(days=2))

        assert [row["id"] for row in _results(shop.api.get(LIST_URL, {"tab": "open"}))] == [sooner.pk, later.pk]

    def test_history_tab_shows_the_newest_order_first(self, shop):
        older = _order(shop, status="COMPLETED", pickup_start_at=timezone.now() + timedelta(days=1))
        newer = _order(shop, status="CANCELLED", pickup_start_at=timezone.now() + timedelta(days=5))

        assert [row["id"] for row in _results(shop.api.get(LIST_URL, {"tab": "history"}))] == [newer.pk, older.pk]

    def test_explicit_ordering(self, shop):
        later = _order(shop, pickup_start_at=timezone.now() + timedelta(days=4))
        sooner = _order(shop, pickup_start_at=timezone.now() + timedelta(days=2))

        rows = _results(shop.api.get(LIST_URL, {"ordering": "-created_at"}))

        assert [row["id"] for row in rows] == [sooner.pk, later.pk]

    def test_filters_by_statuses_farmer_and_pickup_dates(self, shop):
        placed = _order(shop)
        accepted = _order(shop, status="ACCEPTED")
        _order(shop, status="READY_FOR_PICKUP")
        other_farmer = make_order(customer=shop.customer, product=make_product(farmer=make_farmer()))
        far = _order(shop, pickup_start_at=timezone.now() + timedelta(days=6))

        by_status = {row["id"] for row in _results(shop.api.get(LIST_URL, {"status": "PLACED,ACCEPTED"}))}
        by_farmer = {row["id"] for row in _results(shop.api.get(LIST_URL, {"farmer_id": other_farmer.farmer_id}))}
        by_date = {row["id"] for row in _results(shop.api.get(LIST_URL, {"pickup_from": far.pickup_date.isoformat()}))}

        assert by_status == {placed.pk, accepted.pk, other_farmer.pk, far.pk}
        assert by_farmer == {other_farmer.pk}
        assert by_date == {far.pk}
        assert _results(shop.api.get(LIST_URL, {"pickup_to": (far.pickup_date - timedelta(days=1)).isoformat()}))

    @pytest.mark.parametrize("query", [
        {"tab": "all"}, {"status": "SHIPPED"}, {"ordering": "total_amount"}, {"pickup_from": "tomorrow"},
        {"farmer_id": "abc"},
    ])
    def test_invalid_query_is_rejected(self, shop, query):
        response = shop.api.get(LIST_URL, query)

        assert (response.status_code, response.json()["code"]) == (400, "VALIDATION_ERROR")

    def test_constant_number_of_queries(self, shop, django_assert_max_num_queries):
        for _ in range(5):
            _order(shop)

        with django_assert_max_num_queries(8):
            assert len(_results(shop.api.get(LIST_URL))) == 5

    def test_farmer_is_forbidden(self, shop):
        assert _client(shop.farmer.user).get(LIST_URL).status_code == 403

    @pytest.mark.parametrize("status, starts_in, expected", [
        ("PLACED", timedelta(hours=1), True),
        ("PLACED", timedelta(hours=3), False),
        ("ACCEPTED", timedelta(hours=1), False),
    ])
    def test_is_expiring_soon_flags_placed_orders_two_hours_before_pickup(self, shop, status, starts_in, expected):
        # v1.8 OrderSummary.is_expiring_soon: PLACED and at most 2 hours before pickup_start_at.
        _order(shop, status=status, pickup_start_at=timezone.now() + starts_in)

        assert _results(shop.api.get(LIST_URL))[0]["is_expiring_soon"] is expected


@pytest.mark.django_db
class TestOrderDetail:
    def test_returns_order_detail(self, shop):
        order = _order(shop, quantity=3)
        record_order_placed(order=order, actor=shop.customer)

        response = shop.api.get(_detail_url(order))

        assert response.status_code == 200
        data = response.json()["data"]
        assert set(data) == DETAIL_KEYS
        assert "email" not in data["customer"]
        [item] = data["items"]
        assert (item["product_id"], item["quantity"], item["unit_price"], item["product_image"]) == (
            shop.product.pk, 3, "2.50", None
        )
        [placed] = data["status_history"]
        assert (placed["from_status"], placed["to_status"], placed["transition"]) == (None, "PLACED", "T1")
        assert (placed["actor_role"], placed["actor_name"]) == ("CUSTOMER", shop.customer.customer_profile.full_name)
        assert (data["pending_change"], data["review_state"]) == (None, None)

    def test_system_reasons_are_translated_and_admin_name_is_hidden(self, shop):
        order = _order(shop, status="EXPIRED")
        OrderStatusHistory.objects.create(order=order, from_status="PLACED", to_status="EXPIRED",
                                          transition=Transition.T8, actor_role=ActorRole.SYSTEM,
                                          change_reason=ChangeReason.SYSTEM_EXPIRED)

        [expired] = shop.api.get(_detail_url(order)).json()["data"]["status_history"]

        assert expired["actor_name"] is None
        assert expired["change_reason"] == "The order expired because the farmer did not confirm it before pickup."

    def test_farmer_actor_is_shown_by_stall_name(self, shop):
        order = _order(shop, status="ACCEPTED")
        OrderStatusHistory.objects.create(order=order, from_status="PLACED", to_status="ACCEPTED",
                                          transition=Transition.T2, actor=shop.farmer.user, actor_role=ActorRole.FARMER)

        [accepted] = shop.api.get(_detail_url(order)).json()["data"]["status_history"]

        assert accepted["actor_name"] == shop.farmer.stall_name

    def test_pending_change_is_exposed(self, shop):
        order = _order(shop, status="ACCEPTED")
        order.pending_change = {"note": "Ring me"}
        order.save()

        data = shop.api.get(_detail_url(order)).json()["data"]

        # v1.8: items = null means "items unchanged"; the estimate is then the current total.
        assert data["has_pending_change"] is True
        assert (data["pending_change"]["note"], data["pending_change"]["items"]) == ("Ring me", None)
        assert data["pending_change"]["estimated_total"] == data["total_amount"]

    @pytest.mark.parametrize("status, before_cutoff, actions", [
        ("PLACED", True, ["MODIFY", "CANCEL"]),
        ("PLACED", False, []),
        ("ACCEPTED", True, ["REQUEST_CHANGE", "CANCEL"]),
        ("ACCEPTED", False, []),
        ("READY_FOR_PICKUP", True, []),
        ("CANCELLED", True, ["REORDER"]),
        ("DECLINED", True, ["REORDER"]),
        ("NO_SHOW", True, ["REORDER"]),
        ("EXPIRED", True, ["REORDER"]),
        ("COMPLETED", True, ["REVIEW", "REORDER"]),
    ])
    def test_allowed_actions(self, shop, status, before_cutoff, actions):
        # make_order puts cutoff 12 h before pickup; a pickup 6 h away is already past cutoff.
        start = timezone.now() + (timedelta(days=3) if before_cutoff else timedelta(hours=6))
        order = _order(shop, status=status, pickup_start_at=start)

        assert shop.api.get(_detail_url(order)).json()["data"]["allowed_actions"] == actions

    def test_review_state_for_completed_orders(self, shop):
        order = _order(shop, status="COMPLETED")
        item = order.items.get()

        before = shop.api.get(_detail_url(order)).json()["data"]
        FarmerReview.objects.create(order=order, rating=5)
        ProductReview.objects.create(order_item=item, rating=4)
        after = shop.api.get(_detail_url(order)).json()["data"]

        assert before["review_state"] == {"farmer_reviewed": False, "items_pending_review": [item.pk]}
        assert after["review_state"] == {"farmer_reviewed": True, "items_pending_review": []}
        assert after["allowed_actions"] == ["REORDER"]

    def test_another_customers_order_is_not_found(self, shop):
        other = make_order(customer=make_customer(), product=shop.product)

        assert shop.api.get(_detail_url(other)).status_code == 404


@pytest.mark.django_db
class TestCancelOrder:
    def test_cancelling_a_placed_order_keeps_stock(self, shop):
        order = _order(shop, quantity=2)

        response = _cancel(shop.api, order, body={"reason": "Changed my plans"})

        assert response.status_code == 200
        data = response.json()["data"]
        assert (data["status"], data["version"], data["allowed_actions"]) == ("CANCELLED", 2, ["REORDER"])
        assert data["status_history"][-1]["transition"] == "T5"
        shop.product.refresh_from_db()
        assert shop.product.stock_quantity == 10

    def test_cancelling_an_accepted_order_returns_its_stock(self, shop):
        order = _order(shop, quantity=2, status="ACCEPTED")

        response = _cancel(shop.api, order)

        assert (response.status_code, response.json()["data"]["status"]) == (200, "CANCELLED")
        shop.product.refresh_from_db()
        assert shop.product.stock_quantity == 12

    def test_if_match_is_required(self, shop):
        response = _cancel(shop.api, _order(shop), version=False)

        assert (response.status_code, response.json()["code"]) == (428, "PRECONDITION_REQUIRED")

    def test_stale_version_is_rejected(self, shop):
        response = _cancel(shop.api, _order(shop), version=7)

        assert (response.status_code, response.json()["code"]) == (409, "RESOURCE_MODIFIED")

    def test_after_cutoff_is_rejected(self, shop):
        order = _order(shop, pickup_start_at=timezone.now() + timedelta(hours=6))

        response = _cancel(shop.api, order)

        assert (response.status_code, response.json()["code"]) == (422, "CUTOFF_PASSED")

    def test_finished_order_cannot_be_cancelled(self, shop):
        response = _cancel(shop.api, _order(shop, status="COMPLETED"))

        assert (response.status_code, response.json()["code"]) == (400, "INVALID_STATUS_TRANSITION")

    def test_reason_longer_than_500_is_rejected(self, shop):
        response = _cancel(shop.api, _order(shop), body={"reason": "x" * 501})

        assert (response.status_code, response.json()["code"]) == (400, "VALIDATION_ERROR")

    def test_another_customers_order_is_not_found(self, shop):
        other = make_order(customer=make_customer(), product=shop.product)

        assert _cancel(shop.api, other).status_code == 404
        other.refresh_from_db()
        assert other.status == "PLACED"
