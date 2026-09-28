import pytest
from django.urls import reverse

from reviews.models import FarmerReview, ProductReview

FARMER_URL = "public-farmer-review-list"
PRODUCT_URL = "public-product-review-list"


@pytest.mark.django_db
def test_a_guest_sees_a_farmer_review_with_a_shortened_name(
    api_client, farmer_review, approved_farmer
):
    response = api_client.get(reverse(FARMER_URL, args=[approved_farmer.user_id]))

    assert response.status_code == 200
    row = response.data["data"]["results"][0]
    assert row["rating"] == 2
    assert row["comment"] == "Stall was hard to find."
    assert row["customer_display_name"] == "Test C."
    assert "hidden_reason" not in row
    assert "is_hidden_by_admin" not in row


@pytest.mark.django_db
def test_hidden_reviews_never_reach_a_public_page(api_client, farmer_review, approved_farmer):
    FarmerReview.objects.filter(pk=farmer_review.pk).update(is_hidden_by_admin=True)

    data = api_client.get(reverse(FARMER_URL, args=[approved_farmer.user_id])).data["data"]

    assert data["count"] == 0
    assert data["summary"]["rating_count"] == 0
    assert data["summary"]["rating_avg"] is None


@pytest.mark.django_db
def test_public_reviews_use_ten_per_page(api_client, farmer_review, approved_farmer):
    data = api_client.get(reverse(FARMER_URL, args=[approved_farmer.user_id])).data["data"]

    assert data["page_size"] == 10


@pytest.mark.django_db
def test_the_summary_carries_the_average_and_distribution(
    api_client, completed_order, approved_farmer, market, customer_user, product
):
    from datetime import datetime, time, timedelta

    from django.utils import timezone

    from orders.models import Order, OrderStatus

    FarmerReview.objects.create(order=completed_order, rating=5)
    start = timezone.make_aware(datetime.combine(timezone.localdate(), time(9, 0)))
    second = Order.objects.create(
        customer=customer_user, farmer=approved_farmer, market=market,
        pickup_date=timezone.localdate(), pickup_start_at=start,
        pickup_end_at=start + timedelta(hours=2), cutoff_at=start - timedelta(hours=12),
        status=OrderStatus.COMPLETED, total_amount="5.00",
    )
    FarmerReview.objects.create(order=second, rating=3)

    summary = api_client.get(reverse(FARMER_URL, args=[approved_farmer.user_id])).data["data"][
        "summary"
    ]

    assert summary["rating_count"] == 2
    assert summary["rating_avg"] == 4.0
    assert summary["distribution"] == {"1": 0, "2": 0, "3": 1, "4": 0, "5": 1}


@pytest.mark.django_db
def test_the_summary_ignores_the_rating_filter(api_client, farmer_review, approved_farmer):
    data = api_client.get(
        reverse(FARMER_URL, args=[approved_farmer.user_id]), {"rating": "5"}
    ).data["data"]

    assert data["count"] == 0
    assert data["summary"]["rating_count"] == 1
    assert data["summary"]["rating_avg"] == 2.0


@pytest.mark.django_db
def test_an_out_of_range_rating_filter_is_ignored(api_client, farmer_review, approved_farmer):
    for value in ("0", "6", "abc"):
        data = api_client.get(
            reverse(FARMER_URL, args=[approved_farmer.user_id]), {"rating": value}
        ).data["data"]
        assert data["count"] == 1


@pytest.mark.django_db
def test_a_product_review_names_its_product(api_client, product_review, product):
    row = api_client.get(reverse(PRODUCT_URL, args=[product.id])).data["data"]["results"][0]

    assert row["type"] == "PRODUCT"
    assert row["product"] == {"id": product.id, "name": "Tomato"}
    assert row["rating"] == 5


@pytest.mark.django_db
def test_a_farmer_review_has_no_product(api_client, farmer_review, approved_farmer):
    row = api_client.get(reverse(FARMER_URL, args=[approved_farmer.user_id])).data["data"][
        "results"
    ][0]

    assert row["type"] == "FARMER"
    assert row["product"] is None


@pytest.mark.django_db
def test_hidden_product_reviews_are_left_out(api_client, product_review, product):
    ProductReview.objects.filter(pk=product_review.pk).update(is_hidden_by_admin=True)

    assert api_client.get(reverse(PRODUCT_URL, args=[product.id])).data["data"]["count"] == 0


@pytest.mark.django_db
def test_reviews_of_a_non_public_target_are_a_404(api_client, approved_farmer, product):
    approved_farmer.status = "SUSPENDED"
    approved_farmer.save(update_fields=["status"])

    assert api_client.get(reverse(FARMER_URL, args=[approved_farmer.user_id])).status_code == 404
    assert api_client.get(reverse(PRODUCT_URL, args=[product.id])).status_code == 404


@pytest.mark.django_db
def test_unknown_targets_are_a_404(api_client):
    assert api_client.get(reverse(FARMER_URL, args=[9999])).status_code == 404
    assert api_client.get(reverse(PRODUCT_URL, args=[9999])).status_code == 404
