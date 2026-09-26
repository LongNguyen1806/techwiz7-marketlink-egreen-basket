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
