import pytest
from django.urls import reverse

from catalog.models import Category, Product, Unit
from system.flags import raise_flag
from system.models import AuditAction, AuditLog, FlagTarget, ModerationFlag

LIST_URL = "admin-flag-list"
RESOLVE_URL = "admin-flag-resolve"

NOTE = "Photo does not match the produce described."


@pytest.mark.django_db
def test_flagging_something_puts_it_in_the_queue(admin_client, admin_user):
    response = admin_client.post(
        reverse(LIST_URL),
        {"target_type": FlagTarget.PRODUCT, "target_id": 7, "note": NOTE},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["data"]["note"] == NOTE
    assert response.data["data"]["raised_by"]["email"] == admin_user.email
    assert AuditLog.objects.filter(action=AuditAction.CONTENT_FLAGGED).exists()


@pytest.mark.django_db
def test_the_queue_shows_the_open_items_oldest_first(admin_client, admin_user):
    for target_id in (3, 1, 2):
        ModerationFlag.objects.create(
            target_type=FlagTarget.PRODUCT, target_id=target_id, note=NOTE,
            raised_by=admin_user,
        )

    rows = admin_client.get(reverse(LIST_URL)).data["data"]["results"]

    assert [row["target_id"] for row in rows] == [3, 1, 2]


@pytest.mark.django_db
def test_the_same_thing_cannot_be_queued_twice(admin_client, admin_user):
    ModerationFlag.objects.create(
        target_type=FlagTarget.PRODUCT, target_id=5, note=NOTE, raised_by=admin_user
    )

    response = admin_client.post(
        reverse(LIST_URL),
        {"target_type": FlagTarget.PRODUCT, "target_id": 5, "note": "Again"},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "RESOURCE_IN_USE"


@pytest.mark.django_db
def test_resolving_clears_it_from_the_queue(admin_client, admin_user):
    flag = ModerationFlag.objects.create(
        target_type=FlagTarget.PRODUCT_REVIEW, target_id=9, note=NOTE, raised_by=admin_user
    )

    response = admin_client.post(
        reverse(RESOLVE_URL, args=[flag.id]), {"resolution": "Hidden and stall told."},
        format="json",
    )

    assert response.status_code == 200
    assert admin_client.get(reverse(LIST_URL)).data["data"]["count"] == 0
    assert admin_client.get(reverse(LIST_URL), {"resolved": "true"}).data["data"]["count"] == 1
    assert AuditLog.objects.filter(action=AuditAction.CONTENT_FLAG_RESOLVED).exists()


@pytest.mark.django_db
def test_the_same_thing_can_be_queued_again_after_it_was_resolved(admin_client, admin_user):
    flag = ModerationFlag.objects.create(
        target_type=FlagTarget.PRODUCT, target_id=4, note=NOTE, raised_by=admin_user
    )
    admin_client.post(
        reverse(RESOLVE_URL, args=[flag.id]), {"resolution": "Stall fixed it."}, format="json"
    )

    response = admin_client.post(
        reverse(LIST_URL),
        {"target_type": FlagTarget.PRODUCT, "target_id": 4, "note": "It is wrong again."},
        format="json",
    )

    assert response.status_code == 201


@pytest.mark.django_db
def test_resolving_twice_is_refused(admin_client, admin_user):
    flag = ModerationFlag.objects.create(
        target_type=FlagTarget.FARMER, target_id=2, note=NOTE, raised_by=admin_user
    )
    admin_client.post(
        reverse(RESOLVE_URL, args=[flag.id]), {"resolution": "Spoke to the stall."},
        format="json",
    )

    again = admin_client.post(
        reverse(RESOLVE_URL, args=[flag.id]), {"resolution": "Spoke again."}, format="json"
    )

    assert again.status_code == 400
    assert again.data["code"] == "INVALID_STATUS_TRANSITION"


@pytest.mark.django_db
def test_a_note_is_required(admin_client):
    response = admin_client.post(
        reverse(LIST_URL),
        {"target_type": FlagTarget.PRODUCT, "target_id": 1, "note": "no"},
        format="json",
    )

    assert response.status_code == 400
    assert "note" in response.data["errors"]


@pytest.mark.django_db
def test_a_customer_cannot_reach_the_queue(customer_client):
    assert customer_client.get(reverse(LIST_URL)).status_code == 403


@pytest.mark.django_db
def test_the_dashboard_counts_what_is_waiting(admin_client, admin_user, farmer_user):
    ModerationFlag.objects.create(
        target_type=FlagTarget.PRODUCT, target_id=1, note=NOTE, raised_by=admin_user
    )

    waiting = admin_client.get(reverse("admin-dashboard")).data["data"]["needs_attention"]

    assert waiting["flags_open"] == 1
    assert waiting["stalls_awaiting_approval"] == 1
    assert "customers_at_risk" in waiting
    assert "hidden_products" in waiting




@pytest.mark.django_db
def test_a_flagged_product_carries_a_link_and_a_preview(admin_client, admin_user, approved_farmer):
    category = Category.objects.create(name="Leafy greens", display_order=1)
    product = Product.objects.create(
        farmer=approved_farmer,
        category=category,
        name="Water spinach",
        price="12.00",
        unit=Unit.BUNCH,
        stock_quantity=10,
    )
    raise_flag(
        target_type=FlagTarget.PRODUCT,
        target_id=product.id,
        note="Photo looks borrowed",
        actor=admin_user,
    )

    row = admin_client.get(reverse(LIST_URL)).data["data"]["results"][0]

    assert row["target_url"] == f"/admin/products?product_id={product.id}"
    assert product.name in row["target_preview"]


@pytest.mark.django_db
def test_a_flagged_stall_links_to_its_own_page(admin_client, admin_user, approved_farmer):
    raise_flag(
        target_type=FlagTarget.FARMER,
        target_id=approved_farmer.user_id,
        note="Second complaint this month",
        actor=admin_user,
    )

    row = admin_client.get(reverse(LIST_URL)).data["data"]["results"][0]

    assert row["target_url"] == f"/admin/farmers/{approved_farmer.user_id}"
    assert row["target_preview"] == approved_farmer.stall_name


@pytest.mark.django_db
def test_a_flag_whose_target_is_gone_still_lists(admin_client, admin_user):
    raise_flag(
        target_type=FlagTarget.PRODUCT, target_id=999_999, note="Gone now", actor=admin_user
    )

    row = admin_client.get(reverse(LIST_URL)).data["data"]["results"][0]

    assert row["target_preview"] is None
    assert row["target_url"] is not None


@pytest.mark.django_db
def test_queue_search_matches_the_note_and_the_target_number(admin_client, admin_user):
    raise_flag(
        target_type=FlagTarget.PRODUCT, target_id=321, note="Price looks wrong", actor=admin_user
    )
    raise_flag(
        target_type=FlagTarget.CUSTOMER, target_id=7, note="Duplicate account", actor=admin_user
    )

    by_note = admin_client.get(reverse(LIST_URL), {"q": "price"}).data["data"]
    assert [row["target_id"] for row in by_note["results"]] == [321]

    for term in ("321", "#321"):
        by_id = admin_client.get(reverse(LIST_URL), {"q": term}).data["data"]
        assert [row["target_id"] for row in by_id["results"]] == [321], term

    assert admin_client.get(reverse(LIST_URL), {"q": "nothing"}).data["data"]["count"] == 0
