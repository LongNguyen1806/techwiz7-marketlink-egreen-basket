from calendar import monthrange
from datetime import datetime, time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import FarmerStatus
from catalog.models import Category, Product, Unit
from orders.models import Order, OrderStatus
from system.dashboard import DASHBOARD_DAYS, PENDING_FARMER_LIMIT

URL_NAME = "admin-dashboard"


@pytest.mark.django_db
def test_totals_count_each_population(
    admin_client, approved_farmer, customer_user, market, make_farmer, make_order
):
    make_farmer(email="pending@marketlink.test", stall_name="Pending Stall")
    make_order(pickup_date=timezone.localdate())

    totals = admin_client.get(reverse(URL_NAME)).data["data"]["totals"]

    assert totals["farmers"] == 2
    assert totals["farmers_pending"] == 1
    assert totals["customers"] == 1
    assert totals["markets_active"] == 1
    assert totals["orders"] == 1


@pytest.mark.django_db
def test_deactivated_markets_are_not_counted_as_active(admin_client, market):
    market.is_active = False
    market.save(update_fields=["is_active"])

    assert admin_client.get(reverse(URL_NAME)).data["data"]["totals"]["markets_active"] == 0


@pytest.mark.django_db
def test_orders_by_day_always_has_thirty_buckets(admin_client):
    data = admin_client.get(reverse(URL_NAME)).data["data"]["orders_by_day"]

    assert len(data) == DASHBOARD_DAYS
    # A chart needs an unbroken axis, so empty days appear as zeros.
    assert all(row["count"] == 0 for row in data)
    # DateField serializes to an ISO string.
    assert data[-1]["date"] == str(timezone.localdate())
    assert data[0]["date"] == str(timezone.localdate() - timedelta(days=DASHBOARD_DAYS - 1))


@pytest.mark.django_db
def test_orders_land_in_the_bucket_of_the_day_they_were_created(
    admin_client, market, make_order
):
    make_order(pickup_date=timezone.localdate())
    make_order(pickup_date=timezone.localdate())
    old = make_order(pickup_date=timezone.localdate())
    Order.objects.filter(pk=old.pk).update(
        created_at=timezone.now() - timedelta(days=DASHBOARD_DAYS + 5)
    )

    data = admin_client.get(reverse(URL_NAME)).data["data"]["orders_by_day"]

    assert data[-1]["count"] == 2
    # The backdated order falls outside the 30-day window entirely.
    assert sum(row["count"] for row in data) == 2


@pytest.mark.django_db
def test_orders_by_status_lists_every_status_including_zeros(admin_client, market, make_order):
    make_order(pickup_date=timezone.localdate(), status=OrderStatus.COMPLETED)
    make_order(pickup_date=timezone.localdate(), status=OrderStatus.PLACED)

    rows = admin_client.get(reverse(URL_NAME)).data["data"]["orders_by_status"]

    assert [row["status"] for row in rows] == list(OrderStatus.values)
    counts = {row["status"]: row["count"] for row in rows}
    assert counts["COMPLETED"] == 1
    assert counts["PLACED"] == 1
    assert counts["NO_SHOW"] == 0


@pytest.mark.django_db
def test_pending_farmers_are_the_five_newest(admin_client, make_farmer):
    for index in range(7):
        make_farmer(email=f"pending{index}@marketlink.test", stall_name=f"Stall {index}")
    make_farmer(
        email="approved@marketlink.test", stall_name="Approved Stall", status=FarmerStatus.APPROVED
    )

    rows = admin_client.get(reverse(URL_NAME)).data["data"]["pending_farmers"]

    assert len(rows) == PENDING_FARMER_LIMIT
    assert [row["stall_name"] for row in rows] == [f"Stall {i}" for i in (6, 5, 4, 3, 2)]


@pytest.mark.django_db
def test_a_pending_farmer_row_carries_its_counts(admin_client, make_farmer, market, make_order):
    farmer = make_farmer(email="pending@marketlink.test", stall_name="Pending Stall")
    bucket = Category.objects.create(name="Vegetables", display_order=1)
    Product.objects.create(
        farmer=farmer, category=bucket, name="Tomato", price="2.50", unit=Unit.KG, stock_quantity=4
    )
    Product.objects.create(
        farmer=farmer,
        category=bucket,
        name="Archived kale",
        price="1.00",
        unit=Unit.BUNCH,
        stock_quantity=0,
        is_archived=True,
    )
    make_order(pickup_date=timezone.localdate(), status=OrderStatus.PLACED, farmer=farmer)
    make_order(pickup_date=timezone.localdate(), status=OrderStatus.COMPLETED, farmer=farmer)

    row = admin_client.get(reverse(URL_NAME)).data["data"]["pending_farmers"][0]

    assert row["id"] == farmer.user_id
    assert row["email"] == "pending@marketlink.test"
    assert row["status"] == FarmerStatus.PENDING
    # Archived products are soft-deleted, so only the live catalogue counts.
    assert row["product_count"] == 1
    assert row["open_order_count"] == 1


@pytest.mark.django_db
def test_customer_cannot_reach_the_dashboard(customer_client):
    assert customer_client.get(reverse(URL_NAME)).status_code == 403


# ------------------------------------------------- orders per calendar month
# The dashboard chart steps month by month, so this endpoint has to give whole calendar
# months, including the ones with nothing in them.

MONTH_URL_NAME = "admin-dashboard-orders-by-day"


@pytest.mark.django_db
def test_month_defaults_to_the_current_one_and_has_a_bucket_per_day(admin_client):
    today = timezone.localdate()
    data = admin_client.get(reverse(MONTH_URL_NAME)).data["data"]

    assert data["month"] == today.strftime("%Y-%m")
    assert len(data["days"]) == monthrange(today.year, today.month)[1]
    assert data["days"][0]["date"] == today.replace(day=1)


@pytest.mark.django_db
def test_february_of_a_leap_year_has_twenty_nine_buckets(admin_client):
    data = admin_client.get(reverse(MONTH_URL_NAME), {"month": "2024-02"}).data["data"]

    assert data["month"] == "2024-02"
    assert len(data["days"]) == 29
    assert data["total"] == 0


@pytest.mark.django_db
def test_a_month_counts_only_its_own_orders(admin_client, make_order):
    today = timezone.localdate()
    first_of_this_month = today.replace(day=1)
    inside = make_order(pickup_date=today)
    outside = make_order(pickup_date=today)
    Order.objects.filter(pk=inside.pk).update(
        created_at=timezone.make_aware(datetime.combine(first_of_this_month, time(9, 0)))
    )
    # One second before the month began: the boundary must exclude it.
    Order.objects.filter(pk=outside.pk).update(
        created_at=timezone.make_aware(datetime.combine(first_of_this_month, time.min))
        - timedelta(seconds=1)
    )

    data = admin_client.get(
        reverse(MONTH_URL_NAME), {"month": first_of_this_month.strftime("%Y-%m")}
    ).data["data"]

    assert data["total"] == 1
    assert data["days"][0]["count"] == 1


@pytest.mark.django_db
def test_a_month_that_is_not_a_month_is_rejected(admin_client):
    for value in ("2026-13", "September", "2026/09", "1999-01", "9999-01"):
        response = admin_client.get(reverse(MONTH_URL_NAME), {"month": value})
        assert response.status_code == 400, value
        assert "month" in response.data["errors"]


@pytest.mark.django_db
def test_customer_cannot_read_the_month_chart(customer_client):
    assert customer_client.get(reverse(MONTH_URL_NAME)).status_code == 403
