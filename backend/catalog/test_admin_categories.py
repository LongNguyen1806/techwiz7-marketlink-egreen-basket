import pytest
from django.urls import reverse

from catalog.models import Category, Unit

LIST_URL_NAME = "admin-category-list"
DETAIL_URL_NAME = "admin-category-detail"


@pytest.fixture
def category(db):
    return Category.objects.create(name="Vegetables", icon="carrot", display_order=1)


def _make_product(category, farmer_user):
    from catalog.models import Product

    return Product.objects.create(
        farmer=farmer_user.farmer_profile,
        category=category,
        name="Tomato",
        price="2.50",
        unit=Unit.KG,
        stock_quantity=10,
    )


@pytest.mark.django_db
def test_list_returns_every_category_unpaginated_with_product_count(
    admin_client, category, farmer_user
):
    Category.objects.create(name="Hidden Fruits", display_order=2, is_active=False)
    _make_product(category, farmer_user)

    response = admin_client.get(reverse(LIST_URL_NAME))

    assert response.status_code == 200
    rows = response.data["data"]
    assert isinstance(rows, list)
    assert [row["name"] for row in rows] == ["Vegetables", "Hidden Fruits"]
    assert rows[0]["product_count"] == 1
    assert rows[1]["is_active"] is False


@pytest.mark.django_db
def test_create_category(admin_client):
    response = admin_client.post(
        reverse(LIST_URL_NAME),
        {"name": "Bakery", "icon": "croissant", "display_order": 3},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["data"]["name"] == "Bakery"
    assert response.data["data"]["product_count"] == 0
    assert Category.objects.filter(name="Bakery").exists()


@pytest.mark.django_db
def test_duplicate_name_is_a_field_error(admin_client, category):
    response = admin_client.post(reverse(LIST_URL_NAME), {"name": "Vegetables"}, format="json")

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION_ERROR"
    assert "name" in response.data["errors"]


@pytest.mark.django_db
def test_duplicate_name_check_ignores_letter_case(admin_client, category):
    response = admin_client.post(reverse(LIST_URL_NAME), {"name": "vegetables"}, format="json")

    assert response.status_code == 400
    assert "name" in response.data["errors"]


@pytest.mark.django_db
def test_name_length_is_enforced(admin_client):
    response = admin_client.post(reverse(LIST_URL_NAME), {"name": "A"}, format="json")

    assert response.status_code == 400
    assert "name" in response.data["errors"]


@pytest.mark.django_db
def test_update_renames_and_hides(admin_client, category):
    response = admin_client.patch(
        reverse(DETAIL_URL_NAME, args=[category.id]),
        {"name": "Fresh Vegetables", "is_active": False},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["data"]["name"] == "Fresh Vegetables"
    assert response.data["data"]["is_active"] is False
    assert response.data["data"]["product_count"] == 0


@pytest.mark.django_db
def test_rename_to_its_own_name_is_allowed(admin_client, category):
    response = admin_client.patch(
        reverse(DETAIL_URL_NAME, args=[category.id]),
        {"name": category.name, "display_order": 9},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["data"]["display_order"] == 9


@pytest.mark.django_db
def test_delete_empty_category_returns_204_without_body(admin_client, category):
    response = admin_client.delete(reverse(DETAIL_URL_NAME, args=[category.id]))

    assert response.status_code == 204
    assert not response.data
    assert not Category.objects.filter(pk=category.id).exists()


@pytest.mark.django_db
def test_delete_is_refused_while_products_reference_it(admin_client, category, farmer_user):
    _make_product(category, farmer_user)

    response = admin_client.delete(reverse(DETAIL_URL_NAME, args=[category.id]))

    assert response.status_code == 422
    assert response.data["code"] == "RESOURCE_IN_USE"
    assert Category.objects.filter(pk=category.id).exists()


@pytest.mark.django_db
def test_customer_cannot_reach_the_category_admin(customer_client, category):
    assert customer_client.get(reverse(LIST_URL_NAME)).status_code == 403
    assert customer_client.delete(reverse(DETAIL_URL_NAME, args=[category.id])).status_code == 403




@pytest.mark.django_db
def test_icon_must_be_one_of_the_known_set(admin_client):
    response = admin_client.post(
        reverse(LIST_URL_NAME), {"name": "Bakery", "icon": "bread"}, format="json"
    )

    assert response.status_code == 400
    assert "icon" in response.data["errors"]
    assert not Category.objects.filter(name="Bakery").exists()


@pytest.mark.django_db
def test_icon_is_required(admin_client):
    response = admin_client.post(reverse(LIST_URL_NAME), {"name": "Bakery"}, format="json")

    assert response.status_code == 400
    assert "icon" in response.data["errors"]


@pytest.mark.django_db
def test_two_categories_cannot_share_an_icon(admin_client, category):
    response = admin_client.post(
        reverse(LIST_URL_NAME), {"name": "Root vegetables", "icon": "carrot"}, format="json"
    )

    assert response.status_code == 400
    assert "icon" in response.data["errors"]
    assert Category.objects.count() == 1


@pytest.mark.django_db
def test_keeping_its_own_icon_while_renaming_is_allowed(admin_client, category):
    response = admin_client.patch(
        reverse(DETAIL_URL_NAME, args=[category.id]),
        {"name": "Fresh vegetables", "icon": "carrot"},
        format="json",
    )

    assert response.status_code == 200
    category.refresh_from_db()
    assert category.name == "Fresh vegetables"
    assert category.icon == "carrot"


@pytest.mark.django_db
def test_an_icon_freed_by_a_deletion_can_be_reused(admin_client, category):
    admin_client.delete(reverse(DETAIL_URL_NAME, args=[category.id]))

    response = admin_client.post(
        reverse(LIST_URL_NAME), {"name": "Root vegetables", "icon": "carrot"}, format="json"
    )

    assert response.status_code == 201


@pytest.mark.django_db
def test_a_legacy_icon_name_is_stored_in_its_current_form(admin_client):
    response = admin_client.post(
        reverse(LIST_URL_NAME), {"name": "Spices", "icon": "pepper"}, format="json"
    )

    assert response.status_code == 201
    assert Category.objects.get(name="Spices").icon == "chilli"
