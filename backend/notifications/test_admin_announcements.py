from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from notifications.models import Announcement, AnnouncementAudience

LIST_URL_NAME = "admin-announcement-list"
DETAIL_URL_NAME = "admin-announcement-detail"


@pytest.fixture
def window():
    starts_at = timezone.now()
    return starts_at, starts_at + timedelta(days=7)


@pytest.fixture
def announcement(db, admin_user, window):
    starts_at, ends_at = window
    return Announcement.objects.create(
        title="Market closed on Monday",
        content="The central market is closed for maintenance.",
        audience=AnnouncementAudience.ALL,
        starts_at=starts_at,
        ends_at=ends_at,
        created_by=admin_user,
    )


@pytest.mark.django_db
def test_list_is_paginated_and_names_the_author(admin_client, announcement, admin_user):
    response = admin_client.get(reverse(LIST_URL_NAME))

    assert response.status_code == 200
    data = response.data["data"]
    assert {"count", "page", "page_size", "total_pages", "results"} <= data.keys()
    row = data["results"][0]
    assert row["title"] == announcement.title
    assert row["created_by_name"] == admin_user.email
    assert row["audience"] == "ALL"


@pytest.mark.django_db
def test_create_records_the_signed_in_admin_as_author(admin_client, admin_user, window):
    starts_at, ends_at = window

    response = admin_client.post(
        reverse(LIST_URL_NAME),
        {
            "title": "Harvest festival",
            "content": "Join us this weekend.",
            "audience": AnnouncementAudience.CUSTOMER,
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["data"]["created_by_name"] == admin_user.email
    created = Announcement.objects.get(title="Harvest festival")
    assert created.created_by == admin_user


@pytest.mark.django_db
def test_open_ended_announcement_is_allowed(admin_client, window):
    starts_at, _ = window

    response = admin_client.post(
        reverse(LIST_URL_NAME),
        {
            "title": "Permanent notice",
            "content": "Cash on pickup only.",
            "audience": AnnouncementAudience.ALL,
            "starts_at": starts_at.isoformat(),
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["data"]["ends_at"] is None


@pytest.mark.django_db
def test_end_before_start_is_rejected(admin_client, window):
    starts_at, _ = window

    response = admin_client.post(
        reverse(LIST_URL_NAME),
        {
            "title": "Broken window",
            "content": "This should not be accepted.",
            "audience": AnnouncementAudience.ALL,
            "starts_at": starts_at.isoformat(),
            "ends_at": (starts_at - timedelta(hours=1)).isoformat(),
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION_ERROR"
    assert "ends_at" in response.data["errors"]


@pytest.mark.django_db
def test_patching_only_the_end_still_checks_against_the_stored_start(
    admin_client, announcement
):
    response = admin_client.patch(
        reverse(DETAIL_URL_NAME, args=[announcement.id]),
        {"ends_at": (announcement.starts_at - timedelta(hours=1)).isoformat()},
        format="json",
    )

    assert response.status_code == 400
    assert "ends_at" in response.data["errors"]


@pytest.mark.django_db
def test_short_title_is_rejected(admin_client, window):
    starts_at, _ = window

    response = admin_client.post(
        reverse(LIST_URL_NAME),
        {"title": "Hi", "content": "Too short.", "audience": "ALL", "starts_at": starts_at.isoformat()},
        format="json",
    )

    assert response.status_code == 400
    assert "title" in response.data["errors"]


@pytest.mark.django_db
def test_toggle_active(admin_client, announcement):
    response = admin_client.patch(
        reverse(DETAIL_URL_NAME, args=[announcement.id]), {"is_active": False}, format="json",
    )

    assert response.status_code == 200
    assert response.data["data"]["is_active"] is False


@pytest.mark.django_db
def test_delete_returns_204_without_body(admin_client, announcement):
    response = admin_client.delete(reverse(DETAIL_URL_NAME, args=[announcement.id]))

    assert response.status_code == 204
    assert not response.data
    assert not Announcement.objects.filter(pk=announcement.id).exists()


@pytest.mark.django_db
def test_customer_cannot_reach_the_announcement_admin(customer_client, announcement):
    assert customer_client.get(reverse(LIST_URL_NAME)).status_code == 403
    assert customer_client.delete(reverse(DETAIL_URL_NAME, args=[announcement.id])).status_code == 403
