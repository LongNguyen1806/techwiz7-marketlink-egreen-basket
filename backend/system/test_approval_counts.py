from datetime import time

import pytest
from django.urls import reverse
from rest_framework.test import APIClient

from accounts.models import FarmerStatus
from catalog.models import Category, Product, ReviewStatus, Unit
from markets.models import FarmerMarket, FarmerMarketStatus, Market

URL = "admin-approval-counts"


def _market(name: str) -> Market:
    return Market.objects.create(
        name=name,
        address=f"{name} address",
        latitude="10.770000",
        longitude="106.700000",
        open_time=time(6, 0),
        close_time=time(12, 0),
    )


@pytest.mark.django_db
def test_the_total_adds_up_every_kind_of_approval(admin_client, make_farmer):
    make_farmer(email="new1@marketlink.test", stall_name="New One")
    make_farmer(email="new2@marketlink.test", stall_name="New Two")
    seller = make_farmer(email="seller@marketlink.test", stall_name="Seller", status=FarmerStatus.APPROVED)
    category = Category.objects.create(name="Vegetables", icon="carrot", display_order=1)
    for name, review in (("Waiting", ReviewStatus.PENDING), ("On sale", ReviewStatus.APPROVED)):
        Product.objects.create(
            farmer=seller, category=category, name=name, price="2.00", unit=Unit.KG,
            stock_quantity=5, review_status=review,
        )
    FarmerMarket.objects.create(farmer=seller, market=_market("Central Market"), stall_label="A1")
    FarmerMarket.objects.create(
        farmer=seller, market=_market("Riverside Market"), stall_label="B2",
        status=FarmerMarketStatus.PENDING,
    )

    data = admin_client.get(reverse(URL)).data["data"]

    assert data == {"stalls": 2, "products": 1, "markets": 1, "total": 4}


@pytest.mark.django_db
def test_nothing_waiting_is_all_zeros(admin_client):
    assert admin_client.get(reverse(URL)).data["data"] == {
        "stalls": 0, "products": 0, "markets": 0, "total": 0,
    }


@pytest.mark.django_db
def test_only_an_admin_can_read_the_counts(customer_user, farmer_user):
    for user in (customer_user, farmer_user):
        client = APIClient()
        client.force_authenticate(user=user)
        assert client.get(reverse(URL)).status_code == 403


@pytest.mark.django_db
def test_the_dashboard_lists_waiting_market_requests(admin_client, make_farmer):
    seller = make_farmer(email="seller@marketlink.test", stall_name="Seller", status=FarmerStatus.APPROVED)
    FarmerMarket.objects.create(
        farmer=seller, market=_market("Riverside Market"), stall_label="B2",
        status=FarmerMarketStatus.PENDING,
    )

    attention = admin_client.get(reverse("admin-dashboard")).data["data"]["needs_attention"]

    assert attention["market_requests_awaiting_approval"] == 1
