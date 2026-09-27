from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from system.models import AuditAction, AuditLog
from system.services import log_security_event

LIST_URL_NAME = "admin-audit-log-list"
DETAIL_URL_NAME = "admin-audit-log-detail"


def _write(action=AuditAction.EXPORT_DATA, user=None, **overrides):
    payload = {
        "action": action,
        "user": user,
        "endpoint": "/api/admin/reports/export/",
        "method": "GET",
        "ip_address": "10.0.0.1",
        "user_agent": "pytest",
        "status_code": 200,
        "request_id": None,
    }
    payload.update(overrides)
    return log_security_event(**payload)


@pytest.mark.django_db
def test_admin_lists_audit_logs_in_the_paginated_envelope(admin_client, admin_user):
    entry = _write(user=admin_user)

    response = admin_client.get(reverse(LIST_URL_NAME))

    assert response.status_code == 200
    data = response.data["data"]
    assert {"count", "page", "page_size", "total_pages", "next", "previous", "results"} <= data.keys()
    row = next(item for item in data["results"] if item["id"] == entry.id)
    assert row["action"] == AuditAction.EXPORT_DATA
    assert row["method"] == "GET"
    assert row["user"] == {"id": admin_user.id, "email": admin_user.email}


@pytest.mark.django_db
def test_actor_is_null_when_the_event_had_no_user(admin_client):
    entry = _write(action=AuditAction.LOGIN_FAILED, status_code=401)

    response = admin_client.get(reverse(DETAIL_URL_NAME, args=[entry.id]))

    assert response.status_code == 200
    assert response.data["data"]["user"] is None


@pytest.mark.django_db
def test_filters_narrow_by_action_and_actor(admin_client, admin_user, customer_user):
    mine = _write(user=admin_user)
    theirs = _write(action=AuditAction.LOGIN, user=customer_user)

    by_action = admin_client.get(reverse(LIST_URL_NAME), {"action": "export_data"})
    assert [row["id"] for row in by_action.data["data"]["results"]] == [mine.id]

    by_actor = admin_client.get(reverse(LIST_URL_NAME), {"user_id": customer_user.id})
    assert [row["id"] for row in by_actor.data["data"]["results"]] == [theirs.id]


@pytest.mark.django_db
def test_date_range_is_inclusive_on_both_ends(admin_client, admin_user):
    entry = _write(user=admin_user)
    today = timezone.localtime(entry.created_at).date()

    same_day = admin_client.get(
        reverse(LIST_URL_NAME), {"from": today.isoformat(), "to": today.isoformat()},
    )
    assert same_day.data["data"]["count"] == 1

    tomorrow = (today + timedelta(days=1)).isoformat()
    assert admin_client.get(reverse(LIST_URL_NAME), {"from": tomorrow}).data["data"]["count"] == 0


@pytest.mark.django_db
def test_unparsable_date_is_ignored_rather_than_failing(admin_client, admin_user):
    _write(user=admin_user)

    response = admin_client.get(reverse(LIST_URL_NAME), {"from": "not-a-date"})

    assert response.status_code == 200
    assert response.data["data"]["count"] == 1


@pytest.mark.django_db
def test_page_size_accepts_only_the_allowed_values(admin_client, admin_user):
    for _ in range(6):
        _write(user=admin_user)

    assert admin_client.get(reverse(LIST_URL_NAME), {"page_size": 5}).data["data"]["page_size"] == 5
    # 7 is not in ALLOWED_PAGE_SIZES, so it falls back to the default of 20.
    assert admin_client.get(reverse(LIST_URL_NAME), {"page_size": 7}).data["data"]["page_size"] == 20


@pytest.mark.django_db
def test_customer_is_denied_and_the_attempt_is_audited(customer_client, customer_user):
    response = customer_client.get(reverse(LIST_URL_NAME))

    assert response.status_code == 403
    assert response.data["code"] == "PERMISSION_DENIED"
    entry = AuditLog.objects.get(action=AuditAction.ACCESS_DENIED)
    assert entry.user == customer_user
    assert entry.status_code == 403


@pytest.mark.django_db
def test_anonymous_caller_is_rejected(api_client):
    response = api_client.get(reverse(LIST_URL_NAME))

    assert response.status_code in (401, 403)
    assert response.data["success"] is False


@pytest.mark.django_db
def test_audit_logs_sort_by_action_and_reject_unknown_columns(admin_client, admin_user):
    for action in (AuditAction.LOGIN, AuditAction.EXPORT_DATA, AuditAction.ACCESS_DENIED):
        AuditLog.objects.create(user=admin_user, action=action, status_code=200)

    def actions(ordering):
        response = admin_client.get(reverse(LIST_URL_NAME), {"ordering": ordering})
        return [row["action"] for row in response.data["data"]["results"]]

    assert actions("action") == sorted(actions("action"))
    assert actions("-action") == sorted(actions("action"), reverse=True)
    assert admin_client.get(reverse(LIST_URL_NAME), {"ordering": "user_agent"}).status_code == 400


@pytest.mark.django_db
def test_sorting_by_actor_tolerates_events_with_no_user(admin_client, admin_user):
    # LOGIN_FAILED and ACCESS_DENIED are recorded with no user at all, so the actor column
    # has NULLs in it and must not break the sort.
    AuditLog.objects.create(user=None, action=AuditAction.LOGIN_FAILED, status_code=401)
    AuditLog.objects.create(user=admin_user, action=AuditAction.LOGIN, status_code=200)

    for ordering in ("user", "-user"):
        response = admin_client.get(reverse(LIST_URL_NAME), {"ordering": ordering})
        assert response.status_code == 200
        assert response.data["data"]["count"] >= 2
