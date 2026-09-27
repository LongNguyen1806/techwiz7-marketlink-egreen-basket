from datetime import datetime, time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import FarmerStatus
from catalog.models import Category, Product, Unit
from markets.models import Market
from notifications.models import Notification, NotificationType
from orders.models import (
    ChangeReason,
    Order,
    OrderItem,
    OrderStatus,
    OrderStatusHistory,
    Transition,
)
from system.models import AuditAction, AuditLog

LIST_URL = "admin-farmer-list"
DETAIL_URL = "admin-farmer-detail"
IMPACT_URL = "admin-farmer-suspension-impact"
APPROVE_URL = "admin-farmer-approve"
REJECT_URL = "admin-farmer-reject"
SUSPEND_URL = "admin-farmer-suspend"
REINSTATE_URL = "admin-farmer-reinstate"

REASON = "Selling produce that is not their own."


@pytest.fixture
def farmer(farmer_user):
    return farmer_user.farmer_profile


@pytest.fixture
def approved_farmer(farmer):
    farmer.status = FarmerStatus.APPROVED
    farmer.save(update_fields=["status"])
    return farmer


@pytest.fixture
def market(db):
    return Market.objects.create(
        name="Central Market",
        address="1 Market Street",
        latitude="10.762622",
        longitude="106.660172",
        open_time=time(6, 0),
        close_time=time(12, 0),
    )


@pytest.fixture
def product(db, approved_farmer):
    category = Category.objects.create(name="Vegetables", display_order=1)
    return Product.objects.create(
        farmer=approved_farmer,
        category=category,
        name="Tomato",
        price="2.50",
        unit=Unit.KG,
        stock_quantity=10,
    )


@pytest.fixture
def make_order(market, approved_farmer, customer_user, product):
    def _make(*, status=OrderStatus.PLACED, quantity=2) -> Order:
        start = timezone.make_aware(datetime.combine(timezone.localdate(), time(8, 0)))
        order = Order.objects.create(
            customer=customer_user,
            farmer=approved_farmer,
            market=market,
            pickup_date=timezone.localdate(),
            pickup_start_at=start,
            pickup_end_at=start + timedelta(hours=2),
            cutoff_at=start - timedelta(hours=12),
            status=status,
            total_amount="5.00",
        )
        OrderItem.objects.create(
            order=order,
            product=product,
            product_name=product.name,
            unit_price=product.price,
            unit=product.unit,
            quantity=quantity,
            line_total="5.00",
        )
        return order

    return _make


@pytest.mark.django_db
def test_the_list_is_paginated_and_carries_the_counts(admin_client, approved_farmer, product):
    response = admin_client.get(reverse(LIST_URL))

    assert response.status_code == 200
    data = response.data["data"]
    assert {"count", "page", "page_size", "total_pages", "results"} <= data.keys()
    row = data["results"][0]
    assert row["id"] == approved_farmer.user_id
    assert row["stall_name"] == "Test Stall"
    assert row["email"] == "farmer@marketlink.test"
    assert row["status"] == FarmerStatus.APPROVED
    assert row["product_count"] == 1
    assert row["open_order_count"] == 0


@pytest.mark.django_db
def test_filters_by_status_search_and_market(admin_client, approved_farmer):
    assert admin_client.get(reverse(LIST_URL), {"status": "APPROVED"}).data["data"]["count"] == 1
    assert admin_client.get(reverse(LIST_URL), {"status": "PENDING"}).data["data"]["count"] == 0
    # An unusable status is ignored rather than rejected.
    assert admin_client.get(reverse(LIST_URL), {"status": "NONSENSE"}).data["data"]["count"] == 1
    assert admin_client.get(reverse(LIST_URL), {"q": "test stall"}).data["data"]["count"] == 1
    assert admin_client.get(reverse(LIST_URL), {"q": "0907654321"}).data["data"]["count"] == 1
    assert admin_client.get(reverse(LIST_URL), {"market_id": "9999"}).data["data"]["count"] == 0


@pytest.mark.django_db
def test_approve_a_pending_farmer_notifies_and_audits(admin_client, farmer, farmer_user, admin_user):
    response = admin_client.post(reverse(APPROVE_URL, args=[farmer.user_id]))

    assert response.status_code == 200
    assert response.data["data"]["status"] == FarmerStatus.APPROVED

    notification = Notification.objects.get(recipient=farmer_user)
    assert notification.type == NotificationType.ACCOUNT_STATUS_CHANGED
    assert "approved" in notification.title

    entry = AuditLog.objects.get(action=AuditAction.FARMER_APPROVED)
    assert entry.user == admin_user
    assert entry.details["farmer_id"] == farmer.user_id


@pytest.mark.django_db
def test_approving_twice_is_an_invalid_transition(admin_client, approved_farmer):
    response = admin_client.post(reverse(APPROVE_URL, args=[approved_farmer.user_id]))

    assert response.status_code == 400
    assert response.data["code"] == "INVALID_STATUS_TRANSITION"
    assert not AuditLog.objects.filter(action=AuditAction.FARMER_APPROVED).exists()


@pytest.mark.django_db
def test_reject_stores_the_reason_in_the_history(admin_client, farmer, admin_user):
    response = admin_client.post(
        reverse(REJECT_URL, args=[farmer.user_id]), {"reason": REASON}, format="json"
    )

    assert response.status_code == 200
    assert response.data["data"]["status"] == FarmerStatus.REJECTED
    farmer.refresh_from_db()
    assert farmer.status_reason == REASON

    trail = admin_client.get(reverse(DETAIL_URL, args=[farmer.user_id])).data["data"][
        "status_history"
    ]
    last = trail[-1]
    assert last["to_status"] == FarmerStatus.REJECTED
    assert last["reason"] == REASON
    assert last["changed_by"] == admin_user.email


@pytest.mark.django_db
def test_reject_requires_a_reason(admin_client, farmer):
    for body in ({}, {"reason": "bad"}):
        response = admin_client.post(reverse(REJECT_URL, args=[farmer.user_id]), body, format="json")
        assert response.status_code == 400
        assert "reason" in response.data["errors"]

    farmer.refresh_from_db()
    assert farmer.status == FarmerStatus.PENDING


@pytest.mark.django_db
def test_an_approved_farmer_cannot_be_rejected(admin_client, approved_farmer):
    response = admin_client.post(
        reverse(REJECT_URL, args=[approved_farmer.user_id]), {"reason": REASON}, format="json"
    )

    assert response.status_code == 400
    assert response.data["code"] == "INVALID_STATUS_TRANSITION"


@pytest.mark.django_db
def test_suspension_impact_counts_open_orders_per_status(
    admin_client, approved_farmer, make_order
):
    make_order(status=OrderStatus.PLACED)
    make_order(status=OrderStatus.ACCEPTED)
    make_order(status=OrderStatus.READY_FOR_PICKUP)
    make_order(status=OrderStatus.COMPLETED)

    data = admin_client.get(reverse(IMPACT_URL, args=[approved_farmer.user_id])).data["data"]

    assert data["open_orders"] == {
        "PLACED": 1,
        "ACCEPTED": 1,
        "READY_FOR_PICKUP": 1,
        "total": 3,
    }
    assert data["affected_customers"] == 1


@pytest.mark.django_db
def test_suspend_declines_every_open_order_and_restores_stock(
    admin_client, approved_farmer, product, make_order, farmer_user, customer_user, admin_user
):
    # D-015 / §5.4: T3, T4 and T12 all land on DECLINED, but only the orders that actually
    # took stock give it back - D-029 means a PLACED order never deducted any.
    placed = make_order(status=OrderStatus.PLACED, quantity=2)
    accepted = make_order(status=OrderStatus.ACCEPTED, quantity=3)
    ready = make_order(status=OrderStatus.READY_FOR_PICKUP, quantity=1)
    finished = make_order(status=OrderStatus.COMPLETED, quantity=5)
    stock_before = product.stock_quantity

    response = admin_client.post(
        reverse(SUSPEND_URL, args=[approved_farmer.user_id]), {"reason": REASON}, format="json"
    )

    assert response.status_code == 200
    assert response.data["data"]["status"] == FarmerStatus.SUSPENDED
    assert response.data["data"]["affected_orders"] == 3

    for order in (placed, accepted, ready):
        order.refresh_from_db()
        assert order.status == OrderStatus.DECLINED
    finished.refresh_from_db()
    assert finished.status == OrderStatus.COMPLETED

    product.refresh_from_db()
    # Only the ACCEPTED (3) and READY_FOR_PICKUP (1) orders held stock; the PLACED one did not.
    assert product.stock_quantity == stock_before + 3 + 1


@pytest.mark.django_db
def test_suspend_writes_the_status_history_with_the_admin_reason_code(
    admin_client, approved_farmer, make_order, admin_user
):
    ready = make_order(status=OrderStatus.READY_FOR_PICKUP)

    admin_client.post(
        reverse(SUSPEND_URL, args=[approved_farmer.user_id]), {"reason": REASON}, format="json"
    )

    row = OrderStatusHistory.objects.get(order=ready)
    assert row.to_status == OrderStatus.DECLINED
    # READY_FOR_PICKUP -> DECLINED is T12, reserved for an admin.
    assert row.transition == Transition.T12
    assert row.actor_role == "ADMIN"
    assert row.actor == admin_user
    assert row.change_reason == ChangeReason.FARMER_SUSPENDED_BY_ADMIN


@pytest.mark.django_db
def test_suspend_notifies_the_customer_and_the_farmer(
    admin_client, approved_farmer, make_order, customer_user, farmer_user
):
    make_order(status=OrderStatus.PLACED)

    admin_client.post(
        reverse(SUSPEND_URL, args=[approved_farmer.user_id]), {"reason": REASON}, format="json"
    )

    assert Notification.objects.filter(
        recipient=customer_user, type=NotificationType.ORDER_DECLINED
    ).exists()
    assert Notification.objects.filter(
        recipient=farmer_user, type=NotificationType.ACCOUNT_STATUS_CHANGED
    ).exists()


@pytest.mark.django_db
def test_suspend_audits_the_reason_and_the_order_count(
    admin_client, approved_farmer, make_order, admin_user
):
    make_order(status=OrderStatus.PLACED)
    make_order(status=OrderStatus.ACCEPTED)

    admin_client.post(
        reverse(SUSPEND_URL, args=[approved_farmer.user_id]), {"reason": REASON}, format="json"
    )

    entry = AuditLog.objects.get(action=AuditAction.FARMER_SUSPENDED)
    assert entry.user == admin_user
    assert entry.details["reason"] == REASON
    assert entry.details["affected_orders"] == 2


@pytest.mark.django_db
def test_suspending_a_quiet_farmer_touches_no_orders(admin_client, approved_farmer):
    response = admin_client.post(
        reverse(SUSPEND_URL, args=[approved_farmer.user_id]), {"reason": REASON}, format="json"
    )

    assert response.status_code == 200
    assert response.data["data"]["affected_orders"] == 0


@pytest.mark.django_db
def test_only_an_approved_farmer_can_be_suspended(admin_client, farmer):
    response = admin_client.post(
        reverse(SUSPEND_URL, args=[farmer.user_id]), {"reason": REASON}, format="json"
    )

    assert response.status_code == 400
    assert response.data["code"] == "INVALID_STATUS_TRANSITION"


@pytest.mark.django_db
def test_a_suspended_farmer_disappears_from_the_public_pages(
    admin_client, api_client, approved_farmer
):
    admin_client.post(
        reverse(SUSPEND_URL, args=[approved_farmer.user_id]), {"reason": REASON}, format="json"
    )

    assert api_client.get(reverse("public-farmer-list")).data["data"]["count"] == 0


@pytest.mark.django_db
def test_reinstate_clears_the_suspension_reason(admin_client, approved_farmer, admin_user):
    admin_client.post(
        reverse(SUSPEND_URL, args=[approved_farmer.user_id]), {"reason": REASON}, format="json"
    )

    response = admin_client.post(reverse(REINSTATE_URL, args=[approved_farmer.user_id]))

    assert response.status_code == 200
    assert response.data["data"]["status"] == FarmerStatus.APPROVED
    approved_farmer.refresh_from_db()
    assert approved_farmer.status_reason is None
    assert AuditLog.objects.filter(action=AuditAction.FARMER_REINSTATED).count() == 1


@pytest.mark.django_db
def test_reinstating_an_active_farmer_is_refused(admin_client, approved_farmer):
    response = admin_client.post(reverse(REINSTATE_URL, args=[approved_farmer.user_id]))

    assert response.status_code == 400
    assert response.data["code"] == "INVALID_STATUS_TRANSITION"


@pytest.mark.django_db
def test_the_detail_carries_products_stats_and_the_trail(
    admin_client, approved_farmer, product, make_order
):
    make_order(status=OrderStatus.COMPLETED)

    data = admin_client.get(reverse(DETAIL_URL, args=[approved_farmer.user_id])).data["data"]

    assert data["email"] == "farmer@marketlink.test"
    assert data["status"] == FarmerStatus.APPROVED
    assert data["status_reason"] is None
    assert [row["name"] for row in data["products"]] == ["Tomato"]
    assert data["order_stats"] == {
        "total": 1,
        "completed": 1,
        "declined": 0,
        "expired": 0,
        "no_show": 0,
    }
    assert isinstance(data["status_history"], list)


@pytest.mark.django_db
def test_the_trail_records_each_status_change_in_order(admin_client, farmer):
    admin_client.post(reverse(APPROVE_URL, args=[farmer.user_id]))
    admin_client.post(
        reverse(SUSPEND_URL, args=[farmer.user_id]), {"reason": REASON}, format="json"
    )
    admin_client.post(reverse(REINSTATE_URL, args=[farmer.user_id]))

    trail = admin_client.get(reverse(DETAIL_URL, args=[farmer.user_id])).data["data"][
        "status_history"
    ]

    assert [(row["from_status"], row["to_status"]) for row in trail] == [
        (None, FarmerStatus.PENDING),
        (FarmerStatus.PENDING, FarmerStatus.APPROVED),
        (FarmerStatus.APPROVED, FarmerStatus.SUSPENDED),
        (FarmerStatus.SUSPENDED, FarmerStatus.APPROVED),
    ]


@pytest.mark.django_db
def test_an_unknown_farmer_is_a_404(admin_client):
    assert admin_client.get(reverse(DETAIL_URL, args=[9999])).status_code == 404
    assert admin_client.get(reverse(IMPACT_URL, args=[9999])).status_code == 404
    assert admin_client.post(reverse(APPROVE_URL, args=[9999])).status_code == 404


@pytest.mark.django_db
def test_customer_cannot_reach_the_farmer_admin(customer_client, approved_farmer):
    assert customer_client.get(reverse(LIST_URL)).status_code == 403
    assert (
        customer_client.post(
            reverse(SUSPEND_URL, args=[approved_farmer.user_id]),
            {"reason": REASON},
            format="json",
        ).status_code
        == 403
    )


@pytest.mark.django_db
def test_suspend_clears_any_pending_change_request(admin_client, approved_farmer, make_order):
    # §5.4 step 4: the request dies with the order it belonged to.
    order = make_order(status=OrderStatus.ACCEPTED)
    Order.objects.filter(pk=order.pk).update(pending_change={"items": []})

    admin_client.post(
        reverse(SUSPEND_URL, args=[approved_farmer.user_id]), {"reason": REASON}, format="json"
    )

    order.refresh_from_db()
    assert order.pending_change is None
    assert order.status == OrderStatus.DECLINED


# ---------------------------------------------------------------------------
# ?ordering= (v1.8). The tables page server-side, so sorting has to be the database's job.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_stalls_sort_by_name_in_both_directions(admin_client, farmer, make_farmer):
    make_farmer(email="aaa@marketlink.test", stall_name="Apple Stall")
    make_farmer(email="zzz@marketlink.test", stall_name="Zucchini Stall")

    def names(ordering):
        response = admin_client.get(reverse(LIST_URL), {"ordering": ordering})
        return [row["stall_name"] for row in response.data["data"]["results"]]

    assert names("stall_name") == sorted(names("stall_name"))
    assert names("-stall_name") == sorted(names("stall_name"), reverse=True)


@pytest.mark.django_db
def test_sorting_orders_the_whole_table_not_just_one_page(admin_client, farmer, make_farmer):
    # The point of sorting server-side: the smallest name must reach page 1 even though it
    # was created last and would sit on the final page under the default order.
    for index in range(5):
        make_farmer(email=f"f{index}@marketlink.test", stall_name=f"Stall {9 - index}")

    response = admin_client.get(reverse(LIST_URL), {"ordering": "stall_name", "page_size": 5})
    first_page = [row["stall_name"] for row in response.data["data"]["results"]]

    assert first_page[0] == "Stall 5"
    assert response.data["data"]["count"] > len(first_page)


@pytest.mark.django_db
def test_an_unknown_sort_column_is_a_400(admin_client):
    response = admin_client.get(reverse(LIST_URL), {"ordering": "user__password"})

    assert response.status_code == 400
    assert response.data["code"] == "VALIDATION_ERROR"
    assert "ordering" in response.data["errors"]


@pytest.mark.django_db
def test_no_ordering_keeps_the_newest_first_default(admin_client, farmer, make_farmer):
    newest = make_farmer(email="new@marketlink.test", stall_name="Newest Stall")

    response = admin_client.get(reverse(LIST_URL))

    assert response.data["data"]["results"][0]["id"] == newest.user_id


# ---------------------------------------------------------------------------
# AD-03 PATCH: the admin corrects a stall's contact details.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_admin_corrects_the_contact_details(admin_client, farmer, admin_user):
    response = admin_client.patch(
        reverse(DETAIL_URL, args=[farmer.user_id]),
        {"stall_name": "Riverside Greens", "contact_person": "Mai Tran"},
        format="json",
    )

    assert response.status_code == 200
    farmer.refresh_from_db()
    assert farmer.stall_name == "Riverside Greens"
    assert farmer.contact_person == "Mai Tran"

    entry = AuditLog.objects.get(action=AuditAction.FARMER_UPDATED)
    assert entry.user == admin_user
    assert sorted(entry.details["changed_fields"]) == ["contact_person", "stall_name"]


@pytest.mark.django_db
def test_a_patch_that_changes_nothing_writes_no_audit_row(admin_client, farmer):
    response = admin_client.patch(
        reverse(DETAIL_URL, args=[farmer.user_id]),
        {"stall_name": farmer.stall_name},
        format="json",
    )

    assert response.status_code == 200
    # Otherwise every stray save would add a line to a log the admin has to read.
    assert not AuditLog.objects.filter(action=AuditAction.FARMER_UPDATED).exists()


@pytest.mark.django_db
def test_the_phone_is_stored_in_its_canonical_form(admin_client, farmer):
    admin_client.patch(
        reverse(DETAIL_URL, args=[farmer.user_id]), {"phone": "+84 90 765 4321"}, format="json"
    )

    farmer.refresh_from_db()
    # D-028 keys accounts by one canonical spelling, so "+84 90 765 4321" must land as 0907654321.
    assert farmer.phone == "0907654321"


@pytest.mark.django_db
def test_a_phone_belonging_to_another_stall_is_a_field_error(admin_client, farmer, make_farmer):
    other = make_farmer(email="rival@marketlink.test", stall_name="Rival Stall")

    response = admin_client.patch(
        reverse(DETAIL_URL, args=[farmer.user_id]), {"phone": other.phone}, format="json"
    )

    # The UNIQUE index would raise an IntegrityError and surface as a 500; this wants a 400
    # the form can show under the phone field.
    assert response.status_code == 400
    assert "phone" in response.data["errors"]


@pytest.mark.django_db
def test_a_phone_used_by_a_shopper_is_allowed_on_a_stall(admin_client, farmer, customer_user):
    shopper_phone = customer_user.customer_profile.phone

    response = admin_client.patch(
        reverse(DETAIL_URL, args=[farmer.user_id]), {"phone": shopper_phone}, format="json"
    )

    # The UNIQUE indexes are per table, and registration only checks within a role, so the
    # admin edit must not be stricter than the form that created the account.
    assert response.status_code == 200
    farmer.refresh_from_db()
    assert farmer.phone == shopper_phone


@pytest.mark.django_db
def test_the_edit_cannot_reach_status_or_operating_days(admin_client, farmer):
    before_status, before_days = farmer.status, list(farmer.operating_days)

    admin_client.patch(
        reverse(DETAIL_URL, args=[farmer.user_id]),
        {"status": FarmerStatus.APPROVED, "operating_days": [1], "latitude": "1.0"},
        format="json",
    )

    farmer.refresh_from_db()
    # Status moves only through approve / suspend (AD-05 to AD-08); operating days and
    # coordinates carry D-031 / D-032 rules that belong to the stall's own profile screen.
    assert farmer.status == before_status
    assert farmer.operating_days == before_days


@pytest.mark.django_db
def test_the_edit_is_recorded_in_the_audit_trail_as_the_admin(admin_client, farmer, admin_user):
    from accounts.models import FarmerProfile

    admin_client.patch(
        reverse(DETAIL_URL, args=[farmer.user_id]), {"contact_person": "Nam Le"}, format="json"
    )

    # history_id as well as history_date: two rows written in the same microsecond would
    # otherwise come back in an arbitrary order and this could read the creation row.
    latest = (
        FarmerProfile.history.filter(user_id=farmer.user_id)
        .order_by("history_date", "history_id")
        .last()
    )
    assert latest.history_user == admin_user
    assert latest.history_change_reason == "Edited by Admin"


@pytest.mark.django_db
def test_editing_an_unknown_stall_is_a_404(admin_client):
    assert admin_client.patch(reverse(DETAIL_URL, args=[9999]), {}, format="json").status_code == 404


# ---------------------------------------------------------------------------
# Paging a sorted list. Every allow-list entry carries a tiebreak for this reason: without
# one, rows sharing a sort value come back in whatever order the database felt like, and a
# row can appear on two pages or on none.
# ---------------------------------------------------------------------------


@pytest.mark.django_db
def test_paging_a_sorted_list_shows_every_row_exactly_once(admin_client, farmer, make_farmer):
    # All the same status on purpose: sorting by it leaves the database free to order the
    # ties however it likes, so only the tiebreak keeps the pages stable.
    for index in range(7):
        make_farmer(email=f"tie{index}@marketlink.test", stall_name=f"Stall {index}")

    seen = []
    for page in (1, 2):
        response = admin_client.get(
            reverse(LIST_URL), {"ordering": "status", "page": page, "page_size": 5}
        )
        assert response.status_code == 200
        seen.extend(row["id"] for row in response.data["data"]["results"])

    total = admin_client.get(reverse(LIST_URL)).data["data"]["count"]
    assert len(seen) == len(set(seen)), "a row was served on two pages"
    assert len(seen) == total, "a row was missed between pages"


@pytest.mark.django_db
def test_descending_reverses_the_whole_sort(admin_client, farmer, make_farmer):
    make_farmer(email="aaa@marketlink.test", stall_name="Apple Stall")
    make_farmer(email="zzz@marketlink.test", stall_name="Zucchini Stall")

    def ids(ordering):
        return [
            row["id"]
            for row in admin_client.get(reverse(LIST_URL), {"ordering": ordering})
            .data["data"]["results"]
        ]

    # Not just the first column flipped: the two orders must be exact mirrors.
    assert ids("-stall_name") == list(reversed(ids("stall_name")))


@pytest.mark.django_db
def test_the_stall_list_downloads_as_csv(admin_client, farmer, admin_user):
    response = admin_client.get(reverse("admin-farmer-export"))

    assert response.status_code == 200
    assert response["Content-Type"].startswith("text/csv")
    assert "attachment" in response["Content-Disposition"]

    body = b"".join(response.streaming_content).decode("utf-8")
    # The byte-order mark keeps Excel from opening Vietnamese names as mojibake.
    assert body.startswith("﻿")
    assert "stall_name" in body
    assert farmer.stall_name in body

    entry = AuditLog.objects.get(action=AuditAction.EXPORT_DATA)
    assert entry.details["export"] == "farmers"


@pytest.mark.django_db
def test_the_export_obeys_the_same_filters_as_the_list(admin_client, farmer, make_farmer):
    make_farmer(email="other@marketlink.test", stall_name="Other Stall")

    response = admin_client.get(reverse("admin-farmer-export"), {"q": "Other"})
    body = b"".join(response.streaming_content).decode("utf-8")

    # What downloads has to be what is on screen, or the file quietly says something else.
    assert "Other Stall" in body
    assert farmer.stall_name not in body
