from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from markets.models import MarketClosure
from orders.models import OrderStatus
from system.models import AuditLog

LIST_URL_NAME = "admin-market-closure-list"
DELETE_URL_NAME = "admin-market-closure-detail"


@pytest.fixture
def today():
    return timezone.localdate()


@pytest.fixture
def closure(market, today):
    return MarketClosure.objects.create(
        market=market,
        start_date=today + timedelta(days=2),
        end_date=today + timedelta(days=4),
        reason="Lunar New Year closure",
    )


@pytest.mark.django_db
def test_list_returns_a_plain_array_of_current_closures(admin_client, market, closure):
    response = admin_client.get(reverse(LIST_URL_NAME, args=[market.id]))

    assert response.status_code == 200
    rows = response.data["data"]
    assert isinstance(rows, list)
    assert rows[0]["reason"] == "Lunar New Year closure"
    assert set(rows[0]) == {"id", "start_date", "end_date", "reason"}


@pytest.mark.django_db
def test_past_closures_are_hidden_unless_asked_for(admin_client, market, today):
    MarketClosure.objects.create(
        market=market, start_date=today - timedelta(days=9), end_date=today - timedelta(days=7)
    )

    assert admin_client.get(reverse(LIST_URL_NAME, args=[market.id])).data["data"] == []
    included = admin_client.get(
        reverse(LIST_URL_NAME, args=[market.id]), {"include_past": "true"}
    )
    assert len(included.data["data"]) == 1


@pytest.mark.django_db
def test_a_closure_running_today_still_counts_as_current(admin_client, market, today):
    MarketClosure.objects.create(
        market=market, start_date=today - timedelta(days=1), end_date=today
    )

    assert len(admin_client.get(reverse(LIST_URL_NAME, args=[market.id])).data["data"]) == 1


@pytest.mark.django_db
def test_create_a_closure(admin_client, market, today):
    response = admin_client.post(
        reverse(LIST_URL_NAME, args=[market.id]),
        {
            "start_date": str(today + timedelta(days=3)),
            "end_date": str(today + timedelta(days=5)),
            "reason": "Storm damage repairs",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["data"]["reason"] == "Storm damage repairs"
    assert MarketClosure.objects.filter(market=market).count() == 1


@pytest.mark.django_db
def test_a_single_day_closure_is_allowed(admin_client, market, today):
    day = str(today + timedelta(days=1))

    response = admin_client.post(
        reverse(LIST_URL_NAME, args=[market.id]),
        {"start_date": day, "end_date": day},
        format="json",
    )

    assert response.status_code == 201
    assert response.data["data"]["reason"] is None


@pytest.mark.django_db
def test_a_closure_starting_today_is_allowed(admin_client, market, today):
    response = admin_client.post(
        reverse(LIST_URL_NAME, args=[market.id]),
        {"start_date": str(today), "end_date": str(today + timedelta(days=1))},
        format="json",
    )

    assert response.status_code == 201


@pytest.mark.django_db
def test_a_closure_cannot_start_in_the_past(admin_client, market, today):
    response = admin_client.post(
        reverse(LIST_URL_NAME, args=[market.id]),
        {"start_date": str(today - timedelta(days=1)), "end_date": str(today + timedelta(days=1))},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION_ERROR"
    assert "start_date" in response.data["errors"]


@pytest.mark.django_db
def test_end_before_start_is_rejected(admin_client, market, today):
    response = admin_client.post(
        reverse(LIST_URL_NAME, args=[market.id]),
        {"start_date": str(today + timedelta(days=5)), "end_date": str(today + timedelta(days=3))},
        format="json",
    )

    assert response.status_code == 400
    assert "end_date" in response.data["errors"]


@pytest.mark.django_db
def test_overlapping_closures_are_rejected(admin_client, market, closure, today):
    response = admin_client.post(
        reverse(LIST_URL_NAME, args=[market.id]),
        {"start_date": str(today + timedelta(days=3)), "end_date": str(today + timedelta(days=6))},
        format="json",
    )

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION_ERROR"
    assert "start_date" in response.data["errors"]
    assert MarketClosure.objects.count() == 1


@pytest.mark.django_db
def test_a_period_that_swallows_an_existing_one_also_overlaps(admin_client, market, closure, today):
    response = admin_client.post(
        reverse(LIST_URL_NAME, args=[market.id]),
        {"start_date": str(today + timedelta(days=1)), "end_date": str(today + timedelta(days=9))},
        format="json",
    )

    assert response.status_code == 400


@pytest.mark.django_db
def test_an_adjacent_period_is_not_an_overlap(admin_client, market, closure, today):
    response = admin_client.post(
        reverse(LIST_URL_NAME, args=[market.id]),
        {"start_date": str(today + timedelta(days=5)), "end_date": str(today + timedelta(days=7))},
        format="json",
    )

    assert response.status_code == 201


@pytest.mark.django_db
def test_a_closure_covering_an_open_order_is_refused(admin_client, market, make_order, today):
    order = make_order(pickup_date=today + timedelta(days=3))

    response = admin_client.post(
        reverse(LIST_URL_NAME, args=[market.id]),
        {"start_date": str(today + timedelta(days=2)), "end_date": str(today + timedelta(days=4))},
        format="json",
    )

    assert response.status_code == 422
    assert response.data["code"] == "RESOURCE_IN_USE"
    assert response.data["errors"]["order_ids"] == [str(order.id)]
    assert not MarketClosure.objects.exists()


@pytest.mark.django_db
def test_a_finished_order_does_not_block_a_closure(admin_client, market, make_order, today):
    make_order(pickup_date=today + timedelta(days=3), status=OrderStatus.COMPLETED)

    response = admin_client.post(
        reverse(LIST_URL_NAME, args=[market.id]),
        {"start_date": str(today + timedelta(days=2)), "end_date": str(today + timedelta(days=4))},
        format="json",
    )

    assert response.status_code == 201


@pytest.mark.django_db
def test_an_order_outside_the_period_does_not_block_it(admin_client, market, make_order, today):
    make_order(pickup_date=today + timedelta(days=9))

    response = admin_client.post(
        reverse(LIST_URL_NAME, args=[market.id]),
        {"start_date": str(today + timedelta(days=2)), "end_date": str(today + timedelta(days=4))},
        format="json",
    )

    assert response.status_code == 201


@pytest.mark.django_db
def test_delete_returns_204_without_body(admin_client, closure):
    response = admin_client.delete(reverse(DELETE_URL_NAME, args=[closure.id]))

    assert response.status_code == 204
    assert not response.data
    assert not MarketClosure.objects.filter(pk=closure.id).exists()


@pytest.mark.django_db
def test_closures_of_an_unknown_market_are_a_404(admin_client, today):
    assert admin_client.get(reverse(LIST_URL_NAME, args=[9999])).status_code == 404
    assert (
        admin_client.post(
            reverse(LIST_URL_NAME, args=[9999]),
            {"start_date": str(today), "end_date": str(today)},
            format="json",
        ).status_code
        == 404
    )
    assert admin_client.delete(reverse(DELETE_URL_NAME, args=[9999])).status_code == 404


@pytest.mark.django_db
def test_a_closure_shows_up_in_upcoming_closures_on_the_market(admin_client, market, closure):
    response = admin_client.get(reverse("admin-market-detail", args=[market.id]))

    closures = response.data["data"]["upcoming_closures"]
    assert [row["id"] for row in closures] == [closure.id]


@pytest.mark.django_db
def test_a_closure_beyond_the_booking_horizon_is_not_upcoming(admin_client, market, today):
    MarketClosure.objects.create(
        market=market, start_date=today + timedelta(days=30), end_date=today + timedelta(days=32)
    )

    response = admin_client.get(reverse("admin-market-detail", args=[market.id]))

    assert response.data["data"]["upcoming_closures"] == []


@pytest.mark.django_db
def test_customer_cannot_reach_the_closure_admin(customer_client, market, closure):
    assert customer_client.get(reverse(LIST_URL_NAME, args=[market.id])).status_code == 403
    assert customer_client.delete(reverse(DELETE_URL_NAME, args=[closure.id])).status_code == 403


@pytest.mark.django_db
def test_closure_periods_are_not_written_to_the_audit_log(admin_client, market, closure, today):
    admin_client.post(
        reverse(LIST_URL_NAME, args=[market.id]),
        {
            "start_date": str(today + timedelta(days=20)),
            "end_date": str(today + timedelta(days=21)),
        },
        format="json",
    )
    admin_client.delete(reverse(DELETE_URL_NAME, args=[closure.id]))

    assert not AuditLog.objects.exists()
