import pytest
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta

from orders.models import OrderStatus

LIST_URL = "admin-order-list"
DETAIL_URL = "admin-order-detail"


@pytest.mark.django_db
def test_admin_can_find_an_order_by_its_number(admin_client, market, make_order):
    order = make_order(pickup_date=timezone.localdate() + timedelta(days=1))

    response = admin_client.get(reverse(LIST_URL), {"q": str(order.id)})

    # Support is read a number off a screen; typing it has to find the order.
    assert response.status_code == 200
    assert [row["id"] for row in response.data["data"]["results"]] == [order.id]


@pytest.mark.django_db
def test_search_also_matches_the_shopper_and_the_stall(
    admin_client, market, make_order, customer_user
):
    make_order(pickup_date=timezone.localdate() + timedelta(days=1))
    profile = customer_user.customer_profile

    by_name = admin_client.get(reverse(LIST_URL), {"q": profile.full_name})
    by_phone = admin_client.get(reverse(LIST_URL), {"q": profile.phone})

    assert by_name.data["data"]["count"] == 1
    assert by_phone.data["data"]["count"] == 1


@pytest.mark.django_db
def test_the_date_filter_reads_the_pickup_day(admin_client, market, make_order):
    today = timezone.localdate()
    make_order(pickup_date=today + timedelta(days=1))

    inside = admin_client.get(
        reverse(LIST_URL), {"from": str(today), "to": str(today + timedelta(days=2))}
    )
    outside = admin_client.get(
        reverse(LIST_URL), {"from": str(today + timedelta(days=5))}
    )

    # Support is asked about the day of collection, not the day the order was created.
    assert inside.data["data"]["count"] == 1
    assert outside.data["data"]["count"] == 0


@pytest.mark.django_db
def test_the_detail_carries_the_items_and_the_timeline(admin_client, market, make_order):
    order = make_order(pickup_date=timezone.localdate() + timedelta(days=1))

    response = admin_client.get(reverse(DETAIL_URL, args=[order.id]))

    assert response.status_code == 200
    assert "items" in response.data["data"]
    assert "status_history" in response.data["data"]


@pytest.mark.django_db
def test_an_unknown_order_is_a_404(admin_client):
    assert admin_client.get(reverse(DETAIL_URL, args=[999999])).status_code == 404


@pytest.mark.django_db
def test_the_order_screens_are_read_only(admin_client, market, make_order):
    order = make_order(pickup_date=timezone.localdate() + timedelta(days=1))

    # D-033: the admin does not act on individual orders. Looking is allowed; changing is not.
    for method, url in (
        ("post", reverse(LIST_URL)),
        ("patch", reverse(DETAIL_URL, args=[order.id])),
        ("delete", reverse(DETAIL_URL, args=[order.id])),
    ):
        assert getattr(admin_client, method)(url).status_code == 405


@pytest.mark.django_db
def test_a_customer_cannot_reach_the_order_admin(customer_client):
    assert customer_client.get(reverse(LIST_URL)).status_code == 403
