from datetime import timedelta

import pytest
from django.conf import settings
from django.urls import reverse
from django.utils import timezone

from marketlink_core.constants import (
    BOOKING_HORIZON_DAYS,
    MAX_PLACED_ORDERS_PER_CUSTOMER,
    MAX_UPLOAD_MB,
)
from notifications.models import Announcement, AnnouncementAudience

URL = "public-announcement-list"
CONFIG_URL = "public-config"


@pytest.fixture
def make_announcement(db, admin_user):
    def _make(*, title, audience=AnnouncementAudience.ALL, **overrides) -> Announcement:
        now = timezone.now()
        return Announcement.objects.create(
            title=title,
            content="Body text.",
            audience=audience,
            starts_at=overrides.pop("starts_at", now - timedelta(hours=1)),
            ends_at=overrides.pop("ends_at", None),
            created_by=admin_user,
            **overrides,
        )

    return _make


@pytest.mark.django_db
def test_a_guest_sees_only_the_notices_for_everyone(api_client, make_announcement):
    make_announcement(title="For everyone")
    make_announcement(title="For customers", audience=AnnouncementAudience.CUSTOMER)
    make_announcement(title="For farmers", audience=AnnouncementAudience.FARMER)

    response = api_client.get(reverse(URL))

    assert response.status_code == 200
    rows = response.data["data"]
    assert isinstance(rows, list)
    assert [row["title"] for row in rows] == ["For everyone"]
    assert set(rows[0]) == {"id", "title", "content", "audience", "starts_at", "ends_at"}


@pytest.mark.django_db
def test_a_customer_also_sees_the_customer_notices(api_client, customer_user, make_announcement):
    make_announcement(title="For everyone")
    make_announcement(title="For customers", audience=AnnouncementAudience.CUSTOMER)
    make_announcement(title="For farmers", audience=AnnouncementAudience.FARMER)
    api_client.force_authenticate(user=customer_user)

    titles = {row["title"] for row in api_client.get(reverse(URL)).data["data"]}

    assert titles == {"For everyone", "For customers"}


@pytest.mark.django_db
def test_a_farmer_also_sees_the_farmer_notices(api_client, farmer_user, make_announcement):
    make_announcement(title="For everyone")
    make_announcement(title="For farmers", audience=AnnouncementAudience.FARMER)
    api_client.force_authenticate(user=farmer_user)

    titles = {row["title"] for row in api_client.get(reverse(URL)).data["data"]}

    assert titles == {"For everyone", "For farmers"}


@pytest.mark.django_db
def test_inactive_future_and_expired_notices_are_hidden(api_client, make_announcement):
    now = timezone.now()
    make_announcement(title="Live")
    make_announcement(title="Switched off", is_active=False)
    make_announcement(title="Not started", starts_at=now + timedelta(hours=2))
    make_announcement(
        title="Already over", starts_at=now - timedelta(days=2), ends_at=now - timedelta(hours=1)
    )

    titles = [row["title"] for row in api_client.get(reverse(URL)).data["data"]]

    assert titles == ["Live"]


@pytest.mark.django_db
def test_a_notice_ending_later_today_is_still_live(api_client, make_announcement):
    make_announcement(title="Ends tonight", ends_at=timezone.now() + timedelta(hours=3))

    assert [row["title"] for row in api_client.get(reverse(URL)).data["data"]] == ["Ends tonight"]


@pytest.mark.django_db
def test_the_newest_notice_comes_first(api_client, make_announcement):
    now = timezone.now()
    make_announcement(title="Older", starts_at=now - timedelta(days=3))
    make_announcement(title="Newer", starts_at=now - timedelta(hours=2))

    assert [row["title"] for row in api_client.get(reverse(URL)).data["data"]] == ["Newer", "Older"]


@pytest.mark.django_db
def test_the_public_config_reports_the_client_limits(api_client):
    data = api_client.get(reverse(CONFIG_URL)).data["data"]

    assert data["ai_chat_enabled"] == settings.AI_CHAT_ENABLED
    assert data["booking_horizon_days"] == BOOKING_HORIZON_DAYS == 7
    assert data["max_upload_mb"] == MAX_UPLOAD_MB == 2
    assert data["max_placed_orders_per_customer"] == getattr(
        settings, "MAX_PLACED_ORDERS_PER_CUSTOMER", MAX_PLACED_ORDERS_PER_CUSTOMER
    ) == 10


@pytest.mark.django_db
def test_the_config_needs_no_authentication(api_client):
    assert api_client.get(reverse(CONFIG_URL)).status_code == 200
