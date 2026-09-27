from datetime import time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import FarmerStatus
from markets.conftest import MONDAY, SATURDAY, WEDNESDAY
from markets.models import Market, PickupSlot
from notifications.models import Notification, NotificationType
from orders.models import OrderStatus
from system.models import AuditAction, AuditLog

LIST_URL_NAME = "admin-market-list"
DETAIL_URL_NAME = "admin-market-detail"
DEACTIVATE_URL_NAME = "admin-market-deactivate"
ACTIVATE_URL_NAME = "admin-market-activate"


def _payload(**overrides):
    body = {
        "name": "Riverside Market",
        "address": "88 Riverside Road",
        "latitude": "10.800000",
        "longitude": "106.700000",
        "operating_days": [MONDAY, SATURDAY],
        "open_time": "07:00",
        "close_time": "13:00",
    }
    body.update(overrides)
    return body


@pytest.mark.django_db
def test_list_is_paginated_and_counts_farmers(admin_client, market, farmer_market):
    Market.objects.create(
        name="Closed Market",
        address="9 Quiet Lane",
        latitude="10.5",
        longitude="106.5",
        open_time=time(6, 0),
        close_time=time(10, 0),
        is_active=False,
    )

    response = admin_client.get(reverse(LIST_URL_NAME))

    assert response.status_code == 200
    data = response.data["data"]
    assert {"count", "page", "page_size", "total_pages", "results"} <= data.keys()
    # AD-14 includes deactivated markets.
    assert data["count"] == 2
    central = next(row for row in data["results"] if row["name"] == "Central Market")
    assert central["operating_days"] == [MONDAY, WEDNESDAY]
    assert central["open_time"] == "06:00"
    assert central["farmer_count"] == 1
    assert central["open_order_count"] == 0
    assert central["upcoming_closures"] == []


@pytest.mark.django_db
def test_pending_farmers_do_not_count(admin_client, market, farmer_market, approved_farmer):
    approved_farmer.status = "PENDING"
    approved_farmer.save(update_fields=["status"])

    response = admin_client.get(reverse(LIST_URL_NAME))

    row = next(r for r in response.data["data"]["results"] if r["name"] == "Central Market")
    assert row["farmer_count"] == 0


@pytest.mark.django_db
def test_open_order_count_ignores_finished_orders(admin_client, market, make_order):
    today = timezone.localdate()
    make_order(pickup_date=today, status=OrderStatus.PLACED)
    make_order(pickup_date=today, status=OrderStatus.ACCEPTED)
    make_order(pickup_date=today, status=OrderStatus.COMPLETED)
    make_order(pickup_date=today, status=OrderStatus.CANCELLED)

    response = admin_client.get(reverse(DETAIL_URL_NAME, args=[market.id]))

    assert response.data["data"]["open_order_count"] == 2


@pytest.mark.django_db
def test_search_matches_name_or_address(admin_client, market):
    assert admin_client.get(reverse(LIST_URL_NAME), {"q": "central"}).data["data"]["count"] == 1
    assert (
        admin_client.get(reverse(LIST_URL_NAME), {"q": "Market Street"}).data["data"]["count"] == 1
    )
    assert admin_client.get(reverse(LIST_URL_NAME), {"q": "nowhere"}).data["data"]["count"] == 0


@pytest.mark.django_db
def test_filter_by_activation_state(admin_client, market):
    market.is_active = False
    market.save(update_fields=["is_active"])

    assert admin_client.get(reverse(LIST_URL_NAME), {"is_active": "false"}).data["data"][
        "count"
    ] == 1
    assert admin_client.get(reverse(LIST_URL_NAME), {"is_active": "true"}).data["data"]["count"] == 0


@pytest.mark.django_db
def test_create_market_with_operating_days(admin_client):
    response = admin_client.post(reverse(LIST_URL_NAME), _payload(), format="json")

    assert response.status_code == 201
    data = response.data["data"]
    assert data["operating_days"] == [MONDAY, SATURDAY]
    assert data["map_provider"] == "OSM"
    assert data["is_active"] is True
    assert data["distance_km"] is None
    assert data["is_favorite"] is None


@pytest.mark.django_db
def test_create_requires_at_least_one_operating_day(admin_client):
    response = admin_client.post(
        reverse(LIST_URL_NAME), _payload(operating_days=[]), format="json"
    )

    assert response.status_code == 400
    assert "operating_days" in response.data["errors"]


@pytest.mark.django_db
def test_close_time_must_follow_open_time(admin_client):
    response = admin_client.post(
        reverse(LIST_URL_NAME), _payload(open_time="13:00", close_time="07:00"), format="json"
    )

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION_ERROR"
    assert "close_time" in response.data["errors"]


@pytest.mark.django_db
def test_duplicate_name_is_a_field_error(admin_client, market):
    response = admin_client.post(
        reverse(LIST_URL_NAME), _payload(name="Central Market"), format="json"
    )

    assert response.status_code == 400
    assert "name" in response.data["errors"]


@pytest.mark.django_db
def test_patching_only_the_open_time_checks_against_the_stored_close_time(admin_client, market):
    response = admin_client.patch(
        reverse(DETAIL_URL_NAME, args=[market.id]), {"open_time": "20:00"}, format="json"
    )

    assert response.status_code == 400
    assert "close_time" in response.data["errors"]


@pytest.mark.django_db
def test_renaming_does_not_touch_pickup_slots(admin_client, market, make_slot):
    slot = make_slot(day_of_week=MONDAY, start=time(7, 0), end=time(9, 0))

    response = admin_client.patch(
        reverse(DETAIL_URL_NAME, args=[market.id]), {"name": "Central Bazaar"}, format="json"
    )

    assert response.status_code == 200
    assert response.data["data"]["deactivated_slot_count"] == 0
    slot.refresh_from_db()
    assert slot.is_active is True
    assert not Notification.objects.exists()


@pytest.mark.django_db
def test_dropping_a_day_disables_the_slots_on_it_and_notifies_the_farmer(
    admin_client, market, make_slot, farmer_user
):
    kept = make_slot(day_of_week=MONDAY, start=time(7, 0), end=time(9, 0))
    dropped = make_slot(day_of_week=WEDNESDAY, start=time(7, 0), end=time(9, 0))

    response = admin_client.patch(
        reverse(DETAIL_URL_NAME, args=[market.id]), {"operating_days": [MONDAY]}, format="json"
    )

    assert response.status_code == 200
    assert response.data["data"]["deactivated_slot_count"] == 1
    kept.refresh_from_db()
    dropped.refresh_from_db()
    assert kept.is_active is True
    assert dropped.is_active is False

    notification = Notification.objects.get(recipient=farmer_user)
    assert notification.type == NotificationType.MARKET_SCHEDULE_CHANGED
    assert "Central Market" in notification.message
    assert notification.target_url == "/farmer/markets"


@pytest.mark.django_db
def test_narrowing_the_hours_disables_the_slots_outside_them(admin_client, market, make_slot):
    early = make_slot(day_of_week=MONDAY, start=time(6, 30), end=time(8, 0))
    late = make_slot(day_of_week=MONDAY, start=time(10, 0), end=time(11, 30))

    response = admin_client.patch(
        reverse(DETAIL_URL_NAME, args=[market.id]),
        {"open_time": "09:00", "close_time": "12:00"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["data"]["deactivated_slot_count"] == 1
    early.refresh_from_db()
    late.refresh_from_db()
    assert early.is_active is False
    assert late.is_active is True


@pytest.mark.django_db
def test_placed_orders_survive_a_schedule_change(admin_client, market, make_slot, make_order):
    make_slot(day_of_week=WEDNESDAY, start=time(7, 0), end=time(9, 0))
    order = make_order(pickup_date=timezone.localdate() + timedelta(days=1))

    admin_client.patch(
        reverse(DETAIL_URL_NAME, args=[market.id]), {"operating_days": [MONDAY]}, format="json"
    )

    order.refresh_from_db()
    assert order.status == OrderStatus.PLACED


@pytest.mark.django_db
def test_already_disabled_slots_are_not_counted_again(admin_client, market, make_slot):
    slot = make_slot(day_of_week=WEDNESDAY, start=time(7, 0), end=time(9, 0))
    PickupSlot.objects.filter(pk=slot.pk).update(is_active=False)

    response = admin_client.patch(
        reverse(DETAIL_URL_NAME, args=[market.id]), {"operating_days": [MONDAY]}, format="json"
    )

    assert response.data["data"]["deactivated_slot_count"] == 0
    assert not Notification.objects.exists()


@pytest.mark.django_db
def test_deactivate_and_activate_a_quiet_market(admin_client, market):
    response = admin_client.post(
        reverse(DEACTIVATE_URL_NAME, args=[market.id]), {"reason": "The market building is being demolished."}, format="json"
    )
    assert response.status_code == 200
    assert response.data["data"]["is_active"] is False

    response = admin_client.post(reverse(ACTIVATE_URL_NAME, args=[market.id]))
    assert response.status_code == 200
    assert response.data["data"]["is_active"] is True


@pytest.mark.django_db
def test_closing_a_market_cancels_the_orders_still_open_there(
    admin_client, market, make_order, customer_user
):
    order = make_order(pickup_date=timezone.localdate() + timedelta(days=1))

    response = admin_client.post(
        reverse(DEACTIVATE_URL_NAME, args=[market.id]), {"reason": "The market building is being demolished."}, format="json"
    )

    assert response.status_code == 200
    assert response.data["data"]["cancelled_orders"] == 1
    market.refresh_from_db()
    order.refresh_from_db()
    assert market.is_active is False
    assert order.status == OrderStatus.DECLINED

    # The shopper is told, and the reason the admin typed is carried through verbatim.
    notification = Notification.objects.get(
        recipient=customer_user, type=NotificationType.MARKET_CLOSED
    )
    assert "demolished" in notification.message


@pytest.mark.django_db
def test_closing_a_market_switches_off_its_pickup_slots(admin_client, market, make_slot):
    slot = make_slot(day_of_week=MONDAY, start=time(7, 0), end=time(9, 0))

    admin_client.post(
        reverse(DEACTIVATE_URL_NAME, args=[market.id]), {"reason": "The market building is being demolished."}, format="json"
    )

    slot.refresh_from_db()
    assert slot.is_active is False
    # Row by row, so the trail records each one (v1.8).
    latest = PickupSlot.history.filter(id=slot.id).order_by("history_date", "history_id").last()
    assert latest.history_change_reason == f"Market #{market.id} closed by Admin (AD-17)"


@pytest.mark.django_db
def test_unknown_market_is_a_404(admin_client):
    assert admin_client.post(reverse(DEACTIVATE_URL_NAME, args=[9999])).status_code == 404
    assert admin_client.get(reverse(DETAIL_URL_NAME, args=[9999])).status_code == 404


@pytest.mark.django_db
def test_put_is_not_allowed(admin_client, market):
    response = admin_client.put(
        reverse(DETAIL_URL_NAME, args=[market.id]), _payload(), format="json"
    )

    assert response.status_code == 405


@pytest.mark.django_db
def test_customer_cannot_reach_the_market_admin(customer_client, market):
    assert customer_client.get(reverse(LIST_URL_NAME)).status_code == 403
    assert customer_client.post(reverse(DEACTIVATE_URL_NAME, args=[market.id])).status_code == 403


# ---------------------------------------------------------------------------
# audit_logs (v1.8): AD-15 -> MARKET_CREATED, AD-16 -> MARKET_UPDATED,
# AD-17 -> MARKET_DEACTIVATED / MARKET_ACTIVATED. Closures (AD-32, AD-33) write nothing.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_creating_a_market_is_audited(admin_client, admin_user):
    response = admin_client.post(reverse(LIST_URL_NAME), _payload(), format="json")

    assert response.status_code == 201
    entry = AuditLog.objects.get(action=AuditAction.MARKET_CREATED)
    assert entry.user == admin_user
    assert entry.status_code == 201
    assert entry.details["market_id"] == response.data["data"]["id"]
    assert entry.details["name"] == "Riverside Market"


@pytest.mark.django_db
def test_a_refused_market_writes_no_audit_row(admin_client, market):
    response = admin_client.post(reverse(LIST_URL_NAME), _payload(name=market.name), format="json")

    assert response.status_code == 400
    assert not AuditLog.objects.filter(action=AuditAction.MARKET_CREATED).exists()


@pytest.mark.django_db
def test_updating_a_market_audits_the_changed_fields_and_slot_count(
    admin_client, market, make_slot
):
    make_slot(day_of_week=WEDNESDAY, start=time(7, 0), end=time(9, 0))

    response = admin_client.patch(
        reverse(DETAIL_URL_NAME, args=[market.id]),
        {"name": "Renamed Market", "operating_days": [MONDAY]},
        format="json",
    )

    assert response.status_code == 200
    entry = AuditLog.objects.get(action=AuditAction.MARKET_UPDATED)
    assert entry.details["market_id"] == market.id
    # Sorted, and operating_days survives update_market() popping it off its own copy.
    assert entry.details["changed_fields"] == ["name", "operating_days"]
    assert entry.details["deactivated_slot_count"] == 1


@pytest.mark.django_db
def test_deactivating_and_reactivating_are_both_audited(admin_client, market):
    admin_client.post(
        reverse(DEACTIVATE_URL_NAME, args=[market.id]), {"reason": "The market building is being demolished."}, format="json"
    )
    admin_client.post(reverse(ACTIVATE_URL_NAME, args=[market.id]))

    assert [entry.action for entry in AuditLog.objects.order_by("id")] == [
        AuditAction.MARKET_DEACTIVATED,
        AuditAction.MARKET_ACTIVATED,
    ]
    closed = AuditLog.objects.get(action=AuditAction.MARKET_DEACTIVATED)
    assert closed.details["market_id"] == market.id
    assert closed.details["reason"] == "The market building is being demolished."
    assert closed.details["cancelled_orders"] == 0


@pytest.mark.django_db
def test_closing_without_a_reason_is_refused_and_writes_no_audit_row(admin_client, market):
    response = admin_client.post(reverse(DEACTIVATE_URL_NAME, args=[market.id]), {}, format="json")

    assert response.status_code == 400
    assert "reason" in response.data["errors"]
    market.refresh_from_db()
    assert market.is_active is True
    assert not AuditLog.objects.exists()


@pytest.mark.django_db
def test_switching_slots_off_is_kept_in_the_audit_trail(admin_client, market, make_slot):
    # QuerySet.update() would skip these history rows, which is why AD-16 saves row by row.
    slot = make_slot(day_of_week=WEDNESDAY, start=time(7, 0), end=time(9, 0))

    admin_client.patch(
        reverse(DETAIL_URL_NAME, args=[market.id]), {"operating_days": [MONDAY]}, format="json"
    )

    latest = PickupSlot.history.filter(id=slot.id).order_by("history_date", "history_id").last()
    assert latest.is_active is False
    assert latest.history_change_reason == f"Market #{market.id} schedule changed by Admin (AD-16)"


@pytest.mark.django_db
def test_markets_sort_by_name_in_both_directions(admin_client, market):
    Market.objects.create(
        name="Alpha Market", address="1 Alpha Road", latitude="10.1", longitude="106.1",
        open_time=time(6, 0), close_time=time(11, 0),
    )
    names = lambda ordering: [  # noqa: E731
        row["name"]
        for row in admin_client.get(reverse(LIST_URL_NAME), {"ordering": ordering})
        .data["data"]["results"]
    ]

    assert names("name") == sorted(names("name"))
    assert names("-name") == sorted(names("name"), reverse=True)
    assert admin_client.get(reverse(LIST_URL_NAME), {"ordering": "secret"}).status_code == 400


REASON = "The market building is being demolished."


@pytest.mark.django_db
def test_closing_a_market_does_not_suspend_its_stalls(
    admin_client, market, farmer_market, approved_farmer
):
    admin_client.post(
        reverse(DEACTIVATE_URL_NAME, args=[market.id]), {"reason": REASON}, format="json"
    )

    approved_farmer.refresh_from_db()
    # A stall may trade at several markets; closing one of them is no fault of the farmer,
    # and SUSPENDED would cut them off everywhere and stain their profile.
    assert approved_farmer.status == FarmerStatus.APPROVED
    assert approved_farmer.status_reason is None


@pytest.mark.django_db
def test_a_stall_with_no_open_orders_is_still_told(
    admin_client, market, farmer_market, farmer_user
):
    admin_client.post(
        reverse(DEACTIVATE_URL_NAME, args=[market.id]), {"reason": REASON}, format="json"
    )

    notification = Notification.objects.get(
        recipient=farmer_user, type=NotificationType.MARKET_CLOSED
    )
    assert "demolished" in notification.message
    assert notification.target_url == "/farmer/markets"


@pytest.mark.django_db
def test_stock_goes_back_when_the_orders_are_cancelled(
    admin_client, market, make_order, make_slot
):
    from catalog.models import Category, Product, Unit
    from orders.models import OrderItem

    order = make_order(pickup_date=timezone.localdate() + timedelta(days=1))
    order.status = OrderStatus.ACCEPTED
    order.save(update_fields=["status"])
    category = Category.objects.create(name="Roots", display_order=1)
    product = Product.objects.create(
        farmer=order.farmer, category=category, name="Beetroot",
        price="3.00", unit=Unit.KG, stock_quantity=4,
    )
    OrderItem.objects.create(
        order=order, product=product, quantity=2, unit_price="3.00",
        line_total="6.00", product_name="Beetroot",
    )

    admin_client.post(
        reverse(DEACTIVATE_URL_NAME, args=[market.id]), {"reason": REASON}, format="json"
    )

    product.refresh_from_db()
    # An ACCEPTED order had taken the stock (D-029), so closing the market must give it back.
    assert product.stock_quantity == 6


@pytest.mark.django_db
def test_a_market_that_is_already_closed_cannot_be_closed_again(admin_client, market):
    admin_client.post(
        reverse(DEACTIVATE_URL_NAME, args=[market.id]), {"reason": REASON}, format="json"
    )

    response = admin_client.post(
        reverse(DEACTIVATE_URL_NAME, args=[market.id]), {"reason": REASON}, format="json"
    )

    # 400, not 422: the error catalogue (§2.5) files INVALID_STATUS_TRANSITION as a 400 and
    # AD-05 to AD-08 all answer with one.
    assert response.status_code == 400
    assert response.data["code"] == "INVALID_STATUS_TRANSITION"


@pytest.mark.django_db
def test_a_finished_order_is_left_alone(admin_client, market, make_order):
    done = make_order(
        pickup_date=timezone.localdate() - timedelta(days=2), status=OrderStatus.COMPLETED
    )

    response = admin_client.post(
        reverse(DEACTIVATE_URL_NAME, args=[market.id]), {"reason": REASON}, format="json"
    )

    done.refresh_from_db()
    assert response.data["data"]["cancelled_orders"] == 0
    assert done.status == OrderStatus.COMPLETED


@pytest.mark.django_db
def test_reopening_switches_the_closure_slots_back_on(admin_client, market, make_slot):
    slot = make_slot(day_of_week=MONDAY, start=time(7, 0), end=time(9, 0))
    admin_client.post(
        reverse(DEACTIVATE_URL_NAME, args=[market.id]), {"reason": REASON}, format="json"
    )

    response = admin_client.post(reverse(ACTIVATE_URL_NAME, args=[market.id]))

    slot.refresh_from_db()
    # Otherwise every farmer has to switch each of their slots back on by hand.
    assert slot.is_active is True
    assert response.data["data"]["restored_slots"] == 1


@pytest.mark.django_db
def test_reopening_leaves_a_slot_the_farmer_had_already_turned_off(
    admin_client, market, make_slot
):
    off_by_farmer = make_slot(day_of_week=MONDAY, start=time(7, 0), end=time(9, 0))
    off_by_farmer.is_active = False
    off_by_farmer.save(update_fields=["is_active"])

    admin_client.post(
        reverse(DEACTIVATE_URL_NAME, args=[market.id]), {"reason": REASON}, format="json"
    )
    response = admin_client.post(reverse(ACTIVATE_URL_NAME, args=[market.id]))

    off_by_farmer.refresh_from_db()
    # The closure never touched it, so reopening must not switch it on for them.
    assert off_by_farmer.is_active is False
    assert response.data["data"]["restored_slots"] == 0


@pytest.mark.django_db
def test_clearing_a_pending_change_is_kept_in_the_order_trail(
    admin_client, market, make_order
):
    from orders.models import Order

    order = make_order(pickup_date=timezone.localdate() + timedelta(days=1))
    order.pending_change = {"items": []}
    order.save(update_fields=["pending_change"])

    admin_client.post(
        reverse(DEACTIVATE_URL_NAME, args=[market.id]), {"reason": REASON}, format="json"
    )

    order.refresh_from_db()
    assert order.pending_change is None
    # QuerySet.update() would have cleared it with no history row at all.
    reasons = [
        row.history_change_reason
        for row in Order.history.filter(id=order.id).order_by("history_date", "history_id")
    ]
    assert any(r and "closed by Admin" in r for r in reasons)


@pytest.mark.django_db
def test_the_admin_note_reaches_the_stalls_by_email(
    admin_client, market, farmer_market, farmer_user, mailoutbox, settings,
    django_capture_on_commit_callbacks,
):
    # notify() defers the mail to on_commit, which a test transaction never reaches, and
    # _send_email hands it to a thread pool. Both have to be unwound to see the message.
    settings.EMAIL_ASYNC = False
    with django_capture_on_commit_callbacks(execute=True):
        admin_client.post(
            reverse(DEACTIVATE_URL_NAME, args=[market.id]),
            {"reason": REASON, "farmer_message": "Please collect your equipment by Friday."},
            format="json",
        )

    sent = [m for m in mailoutbox if farmer_user.email in m.to]
    assert len(sent) == 1
    assert "collect your equipment" in sent[0].body


@pytest.mark.django_db
def test_the_note_is_for_the_stalls_only(
    admin_client, market, make_order, customer_user, mailoutbox, settings,
    django_capture_on_commit_callbacks,
):
    settings.EMAIL_ASYNC = False
    make_order(pickup_date=timezone.localdate() + timedelta(days=1))

    with django_capture_on_commit_callbacks(execute=True):
        admin_client.post(
            reverse(DEACTIVATE_URL_NAME, args=[market.id]),
            {"reason": REASON, "farmer_message": "Please collect your equipment by Friday."},
            format="json",
        )

    to_shopper = [m for m in mailoutbox if customer_user.email in m.to]
    # The note is addressed to the stalls; a shopper reading it would only be confused.
    assert all("collect your equipment" not in m.body for m in to_shopper)


@pytest.mark.django_db
def test_closing_without_a_note_still_works(admin_client, market, farmer_market, mailoutbox):
    response = admin_client.post(
        reverse(DEACTIVATE_URL_NAME, args=[market.id]), {"reason": REASON}, format="json"
    )

    assert response.status_code == 200
    assert response.data["data"]["cancelled_orders"] == 0


@pytest.mark.django_db
def test_a_stall_with_several_orders_is_told_once(
    admin_client, market, make_order, farmer_user, customer_user
):
    for _ in range(3):
        make_order(pickup_date=timezone.localdate() + timedelta(days=1))

    admin_client.post(
        reverse(DEACTIVATE_URL_NAME, args=[market.id]), {"reason": REASON}, format="json"
    )

    for recipient in (farmer_user, customer_user):
        sent = Notification.objects.filter(
            recipient=recipient, type=NotificationType.MARKET_CLOSED
        )
        # One message naming the count, not one message per cancelled order.
        assert sent.count() == 1, f"{recipient.email} got {sent.count()} notifications"
        assert "3 of your orders" in sent.get().message


@pytest.mark.django_db
def test_an_empty_note_leaves_no_blank_section_in_the_email(
    admin_client, market, farmer_market, farmer_user, mailoutbox, settings,
    django_capture_on_commit_callbacks,
):
    settings.EMAIL_ASYNC = False
    with django_capture_on_commit_callbacks(execute=True):
        admin_client.post(
            reverse(DEACTIVATE_URL_NAME, args=[market.id]),
            {"reason": REASON, "farmer_message": "   "},
            format="json",
        )

    sent = [m for m in mailoutbox if farmer_user.email in m.to]
    assert len(sent) == 1
    # Whitespace is not a note; the email must not carry an empty heading for it.
    assert "note from the MarketLink team" not in sent[0].body
