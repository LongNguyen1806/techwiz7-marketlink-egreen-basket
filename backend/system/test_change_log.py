import pytest
from django.urls import reverse

from accounts.models import FarmerStatus

URL_NAME = "admin-change-log"


def _url(model: str, object_id: int) -> str:
    return reverse(URL_NAME, args=[model, object_id])


@pytest.mark.django_db
def test_a_new_record_starts_with_a_created_entry(admin_client, farmer_user):
    profile = farmer_user.farmer_profile

    response = admin_client.get(_url("farmer_profile", profile.user_id))

    assert response.status_code == 200
    entries = response.data["data"]
    assert len(entries) == 1
    assert entries[0]["change_type"] == "CREATED"
    assert entries[0]["changes"] == []


@pytest.mark.django_db
def test_an_edit_shows_the_old_and_the_new_value(admin_client, farmer_user, admin_user):
    profile = farmer_user.farmer_profile
    before = profile.stall_name

    admin_client.patch(
        reverse("admin-farmer-detail", args=[profile.user_id]),
        {"stall_name": "Renamed Stall"},
        format="json",
    )

    entries = admin_client.get(_url("farmer_profile", profile.user_id)).data["data"]
    # Newest first: the screen shows the most recent change at the top.
    assert entries[0]["change_type"] == "UPDATED"
    assert entries[0]["user"]["email"] == admin_user.email
    assert entries[0]["reason"] == "Edited by Admin"
    assert entries[0]["changes"] == [
        {"field": "stall_name", "old": before, "new": "Renamed Stall"}
    ]


@pytest.mark.django_db
def test_a_status_change_is_in_the_trail_too(admin_client, farmer_user):
    profile = farmer_user.farmer_profile

    admin_client.post(reverse("admin-farmer-approve", args=[profile.user_id]))

    entries = admin_client.get(_url("farmer_profile", profile.user_id)).data["data"]
    changed = {change["field"]: change for change in entries[0]["changes"]}
    assert changed["status"]["old"] == FarmerStatus.PENDING
    assert changed["status"]["new"] == FarmerStatus.APPROVED


@pytest.mark.django_db
def test_an_unknown_record_type_is_a_400_listing_the_valid_ones(admin_client, farmer_user):
    response = admin_client.get(_url("nonsense", farmer_user.farmer_profile.user_id))

    assert response.status_code == 400
    assert "model" in response.data["errors"]
    assert "farmer_profile" in response.data["errors"]["model"][0]


@pytest.mark.django_db
def test_an_id_that_never_existed_is_a_404_not_an_empty_history(admin_client):
    # An empty list would read as "this record has never changed", which is a different thing.
    assert admin_client.get(_url("farmer_profile", 9999)).status_code == 404


@pytest.mark.django_db
def test_a_customer_cannot_read_the_trail(customer_client, farmer_user):
    response = customer_client.get(_url("farmer_profile", farmer_user.farmer_profile.user_id))

    assert response.status_code == 403


@pytest.mark.django_db
def test_a_photo_change_is_recorded_as_its_path(admin_client, farmer_user):
    # The history table keeps a FileField as a plain string, so what comes back is the path,
    # not a file object. _json_safe still guards the FieldFile case, because rendering a live
    # empty ImageFieldFile raises rather than returning null.
    profile = farmer_user.farmer_profile
    profile.image = "farmers/photo.jpg"
    profile.save(update_fields=["image", "updated_at"])

    response = admin_client.get(_url("farmer_profile", profile.user_id))

    assert response.status_code == 200
    changed = {change["field"]: change for change in response.data["data"][0]["changes"]}
    assert changed["image"]["new"] == "farmers/photo.jpg"
    assert changed["image"]["old"] == ""


@pytest.mark.django_db
def test_the_history_survives_the_record_being_deleted(admin_client, farmer_user):
    from markets.models import FarmerMarket, Market, PickupSlot
    from datetime import time

    market = Market.objects.create(
        name="Riverside", address="1 River Road", latitude="10.5", longitude="106.5",
        open_time=time(6, 0), close_time=time(12, 0),
    )
    link = FarmerMarket.objects.create(
        farmer=farmer_user.farmer_profile, market=market, stall_label="A1"
    )
    slot = PickupSlot.objects.create(
        farmer_market=link, day_of_week=1, start_time=time(7, 0), end_time=time(9, 0)
    )
    slot_id = slot.pk
    slot.delete()

    response = admin_client.get(_url("pickup_slot", slot_id))

    # FA-10 deletes slots and FA-34 deletes order items; their history is exactly what an
    # admin would want to look at afterwards.
    assert response.status_code == 200
    assert response.data["data"][0]["change_type"] == "DELETED"


@pytest.mark.django_db
def test_only_the_newest_revisions_are_read(admin_client, farmer_user, django_assert_max_num_queries):
    profile = farmer_user.farmer_profile
    for index in range(12):
        profile.contact_person = f"Contact {index}"
        profile.save(update_fields=["contact_person", "updated_at"])

    response = admin_client.get(_url("farmer_profile", profile.user_id))

    assert response.status_code == 200
    # The limit is applied in the query; reading every revision first would not scale for a
    # product whose stock changes with each order.
    assert len(response.data["data"]) <= 50


# ---------------------------------------------------------------------------
# The limit is applied in the query, which makes an off-by-one easy to get wrong: the oldest
# revision still shown has to be diffed against the one before it, and that one must not
# itself appear in the answer.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_the_limit_keeps_the_diff_of_its_oldest_entry(farmer_user):
    from system.selectors import build_change_log
    from accounts.models import FarmerProfile

    profile = farmer_user.farmer_profile
    for name in ('First', 'Second', 'Third', 'Fourth'):
        profile.contact_person = name
        profile.save(update_fields=['contact_person', 'updated_at'])

    entries = build_change_log(FarmerProfile, profile.user_id, limit=2)

    assert len(entries) == 2
    # Oldest of the two shown: it must know it came from 'Second', which is a revision the
    # answer deliberately does not include.
    assert entries[0]['changes'] == [
        {'field': 'contact_person', 'old': 'Second', 'new': 'Third'}
    ]
    assert entries[1]['changes'] == [
        {'field': 'contact_person', 'old': 'Third', 'new': 'Fourth'}
    ]


@pytest.mark.django_db
def test_a_limit_larger_than_the_history_returns_all_of_it(farmer_user):
    from system.selectors import build_change_log
    from accounts.models import FarmerProfile

    profile = farmer_user.farmer_profile
    profile.contact_person = 'Only change'
    profile.save(update_fields=['contact_person', 'updated_at'])

    entries = build_change_log(FarmerProfile, profile.user_id, limit=50)

    # The selector speaks 'type'; the serializer is what renames it to change_type.
    assert [e['type'] for e in entries] == ['CREATED', 'UPDATED']
    assert entries[0]['changes'] == []


@pytest.mark.django_db
def test_values_that_json_cannot_render_are_coerced(admin_client, farmer_user):
    from decimal import Decimal

    profile = farmer_user.farmer_profile
    profile.latitude = Decimal('10.762622')
    profile.longitude = Decimal('106.660172')
    profile.save(update_fields=['latitude', 'longitude', 'updated_at'])

    response = admin_client.get(_url('farmer_profile', profile.user_id))

    assert response.status_code == 200
    changed = {c['field']: c for c in response.data['data'][0]['changes']}
    # Decimal reaches the renderer as a string rather than blowing up or losing precision.
    assert changed['latitude']['new'] == '10.762622'
    assert changed['latitude']['old'] is None


@pytest.mark.django_db
def test_a_shoppers_profile_now_has_a_trail_too(admin_client, customer_user, admin_user):
    from django.urls import reverse as rev

    profile = customer_user.customer_profile
    admin_client.patch(
        rev("admin-customer-detail", args=[profile.user_id]),
        {"full_name": "Linh Pham"},
        format="json",
    )

    response = admin_client.get(_url("customer_profile", profile.user_id))

    # The admin can edit these details, so the before/after has to be readable here as well.
    assert response.status_code == 200
    assert response.data["data"][0]["changes"] == [
        {"field": "full_name", "old": "Test Customer", "new": "Linh Pham"}
    ]
    assert response.data["data"][0]["user"]["email"] == admin_user.email
