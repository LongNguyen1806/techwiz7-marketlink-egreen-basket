import pytest
from django.urls import reverse

from reviews.models import FarmerReview, ProductReview
from reviews.display import short_customer_name
from system.models import AuditAction, AuditLog

LIST_URL_NAME = "admin-review-list"
FARMER_HIDE = "admin-farmer-review-hide"
FARMER_RESTORE = "admin-farmer-review-restore"
PRODUCT_HIDE = "admin-product-review-hide"
PRODUCT_RESTORE = "admin-product-review-restore"


@pytest.mark.parametrize(
    ("full_name", "expected"),
    [
        ("Nguyen Van An", "Nguyen V. A."),
        ("Le Minh Chau", "Le M. C."),
        ("Madonna", "Madonna"),
        ("", "Customer"),
        (None, "Customer"),
    ],
)
def test_display_name_is_shortened(full_name, expected):
    assert short_customer_name(full_name) == expected


@pytest.mark.django_db
def test_list_merges_both_review_tables(admin_client, farmer_review, product_review):
    response = admin_client.get(reverse(LIST_URL_NAME))

    assert response.status_code == 200
    data = response.data["data"]
    assert data["count"] == 2
    kinds = {row["type"] for row in data["results"]}
    assert kinds == {"FARMER", "PRODUCT"}


@pytest.mark.django_db
def test_a_product_review_carries_its_product_and_order(
    admin_client, product_review, completed_order, product
):
    response = admin_client.get(reverse(LIST_URL_NAME), {"type": "PRODUCT"})

    row = response.data["data"]["results"][0]
    assert row["type"] == "PRODUCT"
    assert row["rating"] == 5
    assert row["comment"] == "Very fresh."
    assert row["product"] == {"id": product.id, "name": "Tomato"}
    assert row["order_id"] == completed_order.id
    assert row["customer_display_name"] == "Test C."
    assert row["is_hidden_by_admin"] is False


@pytest.mark.django_db
def test_a_farmer_review_has_no_product(admin_client, farmer_review, completed_order):
    row = admin_client.get(reverse(LIST_URL_NAME), {"type": "FARMER"}).data["data"]["results"][0]

    assert row["type"] == "FARMER"
    assert row["product"] is None
    assert row["order_id"] == completed_order.id


@pytest.mark.django_db
def test_filter_by_type(admin_client, farmer_review, product_review):
    assert admin_client.get(reverse(LIST_URL_NAME), {"type": "FARMER"}).data["data"]["count"] == 1
    assert admin_client.get(reverse(LIST_URL_NAME), {"type": "PRODUCT"}).data["data"]["count"] == 1


@pytest.mark.django_db
def test_an_unknown_type_is_ignored_rather_than_an_error(admin_client, farmer_review, product_review):
    response = admin_client.get(reverse(LIST_URL_NAME), {"type": "SOMETHING"})

    assert response.status_code == 200
    assert response.data["data"]["count"] == 2


@pytest.mark.django_db
def test_filter_by_rating_spans_both_tables(admin_client, farmer_review, product_review):
    assert admin_client.get(reverse(LIST_URL_NAME), {"rating": "2"}).data["data"]["count"] == 1
    assert admin_client.get(reverse(LIST_URL_NAME), {"rating": "5"}).data["data"]["count"] == 1
    assert admin_client.get(reverse(LIST_URL_NAME), {"rating": "3"}).data["data"]["count"] == 0
    assert admin_client.get(reverse(LIST_URL_NAME), {"rating": "9"}).data["data"]["count"] == 2
    assert admin_client.get(reverse(LIST_URL_NAME), {"rating": "abc"}).data["data"]["count"] == 2


@pytest.mark.django_db
def test_filter_by_hidden_state(admin_client, farmer_review, product_review):
    FarmerReview.objects.filter(pk=farmer_review.pk).update(is_hidden_by_admin=True)

    hidden = admin_client.get(reverse(LIST_URL_NAME), {"is_hidden": "true"}).data["data"]
    assert hidden["count"] == 1
    assert hidden["results"][0]["type"] == "FARMER"
    assert admin_client.get(reverse(LIST_URL_NAME), {"is_hidden": "false"}).data["data"]["count"] == 1


@pytest.mark.django_db
def test_page_size_allow_list_applies_to_the_merged_list(admin_client, farmer_review, product_review):
    data = admin_client.get(reverse(LIST_URL_NAME), {"page_size": "5"}).data["data"]
    assert data["page_size"] == 5

    fallback = admin_client.get(reverse(LIST_URL_NAME), {"page_size": "7"}).data["data"]
    assert fallback["page_size"] == 20


@pytest.mark.django_db
def test_hide_a_farmer_review_records_reason_actor_and_audit(
    admin_client, farmer_review, admin_user
):
    response = admin_client.post(
        reverse(FARMER_HIDE, args=[farmer_review.id]), {"reason": "Abusive language"}, format="json"
    )

    assert response.status_code == 200
    assert response.data["data"]["is_hidden_by_admin"] is True
    assert response.data["data"]["hidden_reason"] == "Abusive language"

    farmer_review.refresh_from_db()
    assert farmer_review.hidden_by == admin_user
    assert farmer_review.hidden_at is not None

    entry = AuditLog.objects.get(action=AuditAction.REVIEW_HIDDEN)
    assert entry.details["review_type"] == "FARMER"
    assert entry.details["review_id"] == farmer_review.id
    assert entry.details["reason"] == "Abusive language"


@pytest.mark.django_db
def test_hide_a_product_review(admin_client, product_review):
    response = admin_client.post(
        reverse(PRODUCT_HIDE, args=[product_review.id]), {"reason": "Spam link"}, format="json"
    )

    assert response.status_code == 200
    assert response.data["data"]["type"] == "PRODUCT"
    assert response.data["data"]["is_hidden_by_admin"] is True
    assert AuditLog.objects.get(action=AuditAction.REVIEW_HIDDEN).details["review_type"] == "PRODUCT"


@pytest.mark.django_db
def test_hide_requires_a_reason(admin_client, farmer_review):
    for body in ({}, {"reason": "no"}):
        response = admin_client.post(
            reverse(FARMER_HIDE, args=[farmer_review.id]), body, format="json"
        )
        assert response.status_code == 400
        assert "reason" in response.data["errors"]

    farmer_review.refresh_from_db()
    assert farmer_review.is_hidden_by_admin is False


@pytest.mark.django_db
def test_restore_clears_the_reason_and_audits(admin_client, product_review):
    admin_client.post(
        reverse(PRODUCT_HIDE, args=[product_review.id]), {"reason": "Spam link"}, format="json"
    )

    response = admin_client.post(reverse(PRODUCT_RESTORE, args=[product_review.id]))

    assert response.status_code == 200
    assert response.data["data"]["is_hidden_by_admin"] is False
    assert response.data["data"]["hidden_reason"] is None

    product_review.refresh_from_db()
    assert product_review.hidden_by is None
    assert product_review.hidden_at is None
    assert AuditLog.objects.filter(action=AuditAction.REVIEW_RESTORED).count() == 1


@pytest.mark.django_db
def test_hiding_never_deletes_the_review(admin_client, farmer_review):
    admin_client.post(
        reverse(FARMER_HIDE, args=[farmer_review.id]), {"reason": "Abusive language"}, format="json"
    )

    assert FarmerReview.objects.filter(pk=farmer_review.id).exists()


@pytest.mark.django_db
def test_the_two_id_spaces_do_not_cross(admin_client, farmer_review, product_review):
    admin_client.post(
        reverse(FARMER_HIDE, args=[farmer_review.id]), {"reason": "Abusive language"}, format="json"
    )

    product_review.refresh_from_db()
    assert product_review.is_hidden_by_admin is False


@pytest.mark.django_db
def test_unknown_review_is_a_404(admin_client):
    body = {"reason": "Nothing here"}
    assert admin_client.post(reverse(FARMER_HIDE, args=[9999]), body, format="json").status_code == 404
    assert (
        admin_client.post(reverse(PRODUCT_HIDE, args=[9999]), body, format="json").status_code == 404
    )
    assert admin_client.post(reverse(FARMER_RESTORE, args=[9999])).status_code == 404
    assert admin_client.post(reverse(PRODUCT_RESTORE, args=[9999])).status_code == 404


@pytest.mark.django_db
def test_customer_cannot_reach_the_review_moderation(customer_client, farmer_review):
    assert customer_client.get(reverse(LIST_URL_NAME)).status_code == 403
    assert (
        customer_client.post(
            reverse(FARMER_HIDE, args=[farmer_review.id]), {"reason": "Not allowed"}, format="json"
        ).status_code
        == 403
    )


@pytest.mark.django_db
def test_an_empty_list_is_still_a_valid_page(admin_client):
    data = admin_client.get(reverse(LIST_URL_NAME)).data["data"]

    assert data["count"] == 0
    assert data["results"] == []
    assert ProductReview.objects.count() == 0


@pytest.mark.django_db
def test_reviews_sort_by_rating_across_both_tables(admin_client, farmer_review, product_review):
    def ratings(ordering):
        response = admin_client.get(reverse(LIST_URL_NAME), {"ordering": ordering})
        return [row["rating"] for row in response.data["data"]["results"]]

    assert ratings("rating") == sorted(ratings("rating"))
    assert ratings("-rating") == sorted(ratings("rating"), reverse=True)


@pytest.mark.django_db
def test_reviews_reject_a_column_the_union_does_not_select(admin_client):
    assert admin_client.get(reverse(LIST_URL_NAME), {"ordering": "comment"}).status_code == 400
