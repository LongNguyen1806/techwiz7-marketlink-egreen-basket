"""An admin edit follows the same rules as registration: it cannot save what signing up refuses."""

import pytest
from django.urls import reverse

FARMER_URL = "admin-farmer-detail"
CUSTOMER_URL = "admin-customer-detail"


@pytest.fixture
def farmer(farmer_user):
    return farmer_user.farmer_profile


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("stall_name", "A"),
        ("contact_person", "B"),
        ("phone", "abc"),
        ("phone", "0123456789"),
        ("phone", ""),
    ],
)
def test_a_farmer_edit_is_refused_where_registration_would_be(admin_client, farmer, field, value):
    response = admin_client.patch(
        reverse(FARMER_URL, args=[farmer.user_id]), {field: value}, format="json"
    )

    assert response.status_code == 400
    assert field in response.data["errors"]


@pytest.mark.django_db
def test_a_farmer_phone_is_stored_normalised(admin_client, farmer):
    response = admin_client.patch(
        reverse(FARMER_URL, args=[farmer.user_id]), {"phone": "+84912345678"}, format="json"
    )

    assert response.status_code == 200, response.data
    farmer.refresh_from_db()
    assert farmer.phone == "0912345678"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("full_name", "L"),
        ("address", "abc"),
        ("phone", "12345"),
        ("phone", "0223456789"),
    ],
)
def test_a_customer_edit_is_refused_where_registration_would_be(
    admin_client, customer_user, field, value
):
    response = admin_client.patch(
        reverse(CUSTOMER_URL, args=[customer_user.pk]), {field: value}, format="json"
    )

    assert response.status_code == 400
    assert field in response.data["errors"]


@pytest.mark.django_db
def test_a_valid_customer_edit_still_saves(admin_client, customer_user):
    response = admin_client.patch(
        reverse(CUSTOMER_URL, args=[customer_user.pk]),
        {"full_name": "Linh Pham", "phone": "0987654321", "address": "99 New Street"},
        format="json",
    )

    assert response.status_code == 200, response.data
