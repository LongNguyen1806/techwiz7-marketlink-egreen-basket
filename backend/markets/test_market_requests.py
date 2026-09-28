from datetime import time

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from catalog.models import Category
from markets.conftest import MONDAY
from markets.models import FarmerMarket, FarmerMarketStatus, Market, MarketOperatingDay, PickupSlot
from notifications.models import Notification, NotificationType
from orders.services.pickup_service import _active_slots
from system.models import AuditAction, AuditLog

LIST_URL = "admin-market-request-list"
APPROVE_URL = "admin-market-request-approve"
REJECT_URL = "admin-market-request-reject"
FARMER_MARKETS_URL = "/api/farmer/markets/"
FARMER_PRODUCTS_URL = "/api/farmer/products/"
REASON = "We could not confirm a stall under this number with the market office."


@pytest.fixture
def riverside(db):
    market = Market.objects.create(
        name="Riverside Market",
        address="88 Riverside Road",
        latitude="10.800000",
        longitude="106.700000",
        open_time=time(6, 0),
        close_time=time(12, 0),
    )
    MarketOperatingDay.objects.create(market=market, day_of_week=MONDAY)
    return market


@pytest.fixture
def farmer_client(farmer_user):
    client = APIClient()
    client.force_authenticate(user=farmer_user)
    return client


@pytest.fixture
def pending_request(approved_farmer, riverside):
    request = FarmerMarket.objects.create(
        farmer=approved_farmer,
        market=riverside,
        stall_label="Gate 2, Stall 4",
        status=FarmerMarketStatus.PENDING,
    )
    PickupSlot.objects.create(
        farmer_market=request, day_of_week=MONDAY, start_time=time(7, 0), end_time=time(9, 0)
    )
    return request


def _bookable_market_ids(farmer) -> set[int]:
    return {slot.farmer_market.market_id for slot in _active_slots(farmer)}


@pytest.mark.django_db
def test_joining_a_market_waits_for_approval(farmer_client, approved_farmer, riverside):
    response = farmer_client.post(
        FARMER_MARKETS_URL, {"market_id": riverside.id, "stall_label": "Gate 2"}, format="json"
    )

    assert response.status_code == 201
    assert response.data["data"]["status"] == FarmerMarketStatus.PENDING
    assert FarmerMarket.objects.get(farmer=approved_farmer, market=riverside).status == (
        FarmerMarketStatus.PENDING
    )


@pytest.mark.django_db
def test_a_farmer_can_prepare_slots_while_waiting(farmer_client, approved_farmer, riverside):
    joined = farmer_client.post(
        FARMER_MARKETS_URL, {"market_id": riverside.id, "stall_label": "Gate 2"}, format="json"
    ).data["data"]

    response = farmer_client.post(
        "/api/farmer/pickup-slots/",
        {
            "farmer_market_id": joined["id"],
            "day_of_week": MONDAY,
            "start_time": "07:00",
            "end_time": "09:00",
        },
        format="json",
    )

    assert response.status_code == 201


@pytest.mark.django_db
def test_a_waiting_market_is_not_bookable_but_the_old_one_still_is(
    approved_farmer, farmer_market, make_slot, pending_request, market, riverside
):
    make_slot(day_of_week=MONDAY, start=time(7, 0), end=time(9, 0))

    assert _bookable_market_ids(approved_farmer) == {market.id}


@pytest.mark.django_db
def test_admin_sees_only_waiting_requests(admin_client, farmer_market, pending_request):
    response = admin_client.get(reverse(LIST_URL))

    assert response.status_code == 200
    rows = response.data["data"]["results"]
    assert [row["id"] for row in rows] == [pending_request.id]
    assert rows[0]["market_name"] == "Riverside Market"
    assert rows[0]["stall_label"] == "Gate 2, Stall 4"
    assert rows[0]["stall_name"] == "Test Stall"


@pytest.mark.django_db
def test_the_list_filters_by_search_and_market(admin_client, pending_request, riverside, market):
    assert admin_client.get(reverse(LIST_URL), {"q": "test stall"}).data["data"]["count"] == 1
    assert admin_client.get(reverse(LIST_URL), {"q": "nobody"}).data["data"]["count"] == 0
    assert (
        admin_client.get(reverse(LIST_URL), {"market_id": riverside.id}).data["data"]["count"] == 1
    )
    assert admin_client.get(reverse(LIST_URL), {"market_id": market.id}).data["data"]["count"] == 0


@pytest.mark.django_db
def test_only_an_admin_can_see_or_decide_requests(customer_client, pending_request):
    assert customer_client.get(reverse(LIST_URL)).status_code == 403
    assert customer_client.post(reverse(APPROVE_URL, args=[pending_request.id])).status_code == 403


@pytest.mark.django_db
def test_approving_opens_the_market_to_shoppers(admin_client, approved_farmer, pending_request, riverside):
    response = admin_client.post(reverse(APPROVE_URL, args=[pending_request.id]))

    assert response.status_code == 200
    pending_request.refresh_from_db()
    assert pending_request.status == FarmerMarketStatus.APPROVED
    assert riverside.id in _bookable_market_ids(approved_farmer)
    note = Notification.objects.get(
        recipient=approved_farmer.user, type=NotificationType.STALL_MARKET_APPROVED
    )
    assert "Riverside Market" in note.title
    assert AuditLog.objects.filter(action=AuditAction.STALL_MARKET_APPROVED).count() == 1


@pytest.mark.django_db
def test_refusing_removes_the_request_and_tells_the_farmer_why(
    admin_client, approved_farmer, pending_request
):
    slot_ids = list(pending_request.pickup_slots.values_list("id", flat=True))

    response = admin_client.post(
        reverse(REJECT_URL, args=[pending_request.id]), {"reason": REASON}, format="json"
    )

    assert response.status_code == 200
    assert not FarmerMarket.objects.filter(pk=pending_request.id).exists()
    assert not PickupSlot.objects.filter(pk__in=slot_ids).exists()
    note = Notification.objects.get(
        recipient=approved_farmer.user, type=NotificationType.STALL_MARKET_REJECTED
    )
    assert REASON in note.message
    assert AuditLog.objects.filter(action=AuditAction.STALL_MARKET_REJECTED).count() == 1


@pytest.mark.django_db
def test_refusing_needs_a_reason(admin_client, pending_request):
    response = admin_client.post(reverse(REJECT_URL, args=[pending_request.id]), {}, format="json")

    assert response.status_code == 400
    assert FarmerMarket.objects.filter(pk=pending_request.id).exists()


@pytest.mark.django_db
def test_a_decided_request_cannot_be_decided_again(admin_client, pending_request, farmer_market):
    admin_client.post(reverse(APPROVE_URL, args=[pending_request.id]))

    again = admin_client.post(reverse(APPROVE_URL, args=[pending_request.id]))
    refuse_approved = admin_client.post(
        reverse(REJECT_URL, args=[farmer_market.id]), {"reason": REASON}, format="json"
    )

    assert again.status_code == 422
    assert refuse_approved.status_code == 422
    assert admin_client.post(reverse(APPROVE_URL, args=[99999])).status_code == 404


@pytest.mark.django_db
def test_a_farmer_without_an_approved_market_cannot_list_products(
    farmer_client, approved_farmer, pending_request
):
    category = Category.objects.create(name="Vegetables", icon="carrot", display_order=1)

    response = farmer_client.post(
        FARMER_PRODUCTS_URL,
        {"name": "Tomato", "category_id": category.id, "price": "2.50", "unit": "KG", "stock_quantity": 5},
        format="json",
    )

    assert response.status_code == 422
    profile = farmer_client.get("/api/farmer/profile/").data["data"]
    assert profile["can_list_products"] is False
