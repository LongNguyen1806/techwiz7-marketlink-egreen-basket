from datetime import datetime, time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import FarmerStatus
from catalog.models import Category, Product, Unit
from markets.models import Market
from notifications.models import Notification, NotificationType
from orders.admin_selectors import at_risk_threshold
from orders.models import ChangeReason, Order, OrderItem, OrderStatus, OrderStatusHistory, Transition
from system.models import AuditAction, AuditLog

LIST_URL = "admin-customer-list"
DETAIL_URL = "admin-customer-detail"
IMPACT_URL = "admin-customer-deactivation-impact"
DEACTIVATE_URL = "admin-customer-deactivate"
ACTIVATE_URL = "admin-customer-activate"

REASON = "Repeatedly ordered and never collected."


@pytest.fixture
def approved_farmer(farmer_user):
    profile = farmer_user.farmer_profile
    profile.status = FarmerStatus.APPROVED
    profile.save(update_fields=["status"])
    return profile


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
    def _make(*, status=OrderStatus.PLACED, quantity=2, created_days_ago=0) -> Order:
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
        if created_days_ago:
            Order.objects.filter(pk=order.pk).update(
                created_at=timezone.now() - timedelta(days=created_days_ago)
            )
        return order

    return _make


@pytest.mark.django_db
def test_the_list_is_paginated_and_carries_the_counts(admin_client, customer_user, make_order):
    make_order(status=OrderStatus.PLACED)
    make_order(status=OrderStatus.NO_SHOW)
    make_order(status=OrderStatus.COMPLETED)

    response = admin_client.get(reverse(LIST_URL))

    assert response.status_code == 200
    data = response.data["data"]
    assert {"count", "page", "page_size", "total_pages", "results"} <= data.keys()
    row = data["results"][0]
    assert row["id"] == customer_user.id
    assert row["full_name"] == "Test Customer"
    assert row["email"] == "customer@marketlink.test"
    assert row["is_active"] is True
    assert row["deactivation_reason"] is None
    assert row["total_orders"] == 3
    assert row["open_orders"] == 1
    assert row["no_show_count"] == 1
    assert row["at_risk"] is False


@pytest.mark.django_db
def test_the_at_risk_flag_needs_enough_recent_no_shows(admin_client, customer_user, make_order):
    for _ in range(at_risk_threshold() - 1):
        make_order(status=OrderStatus.NO_SHOW)

    assert admin_client.get(reverse(LIST_URL)).data["data"]["results"][0]["at_risk"] is False

    make_order(status=OrderStatus.NO_SHOW)

    assert admin_client.get(reverse(LIST_URL)).data["data"]["results"][0]["at_risk"] is True


@pytest.mark.django_db
def test_expired_orders_never_make_a_customer_at_risk(admin_client, customer_user, make_order):
    # D-028: an order expires because the farmer did not confirm it, so it is not the
    # customer's fault and must never count.
    for _ in range(at_risk_threshold() + 2):
        make_order(status=OrderStatus.EXPIRED)

    assert admin_client.get(reverse(LIST_URL)).data["data"]["results"][0]["at_risk"] is False


@pytest.mark.django_db
def test_old_failures_fall_outside_the_at_risk_window(admin_client, customer_user, make_order):
    for _ in range(at_risk_threshold()):
        make_order(status=OrderStatus.NO_SHOW, created_days_ago=90)

    assert admin_client.get(reverse(LIST_URL)).data["data"]["results"][0]["at_risk"] is False


@pytest.mark.django_db
def test_completed_orders_never_make_a_customer_at_risk(admin_client, customer_user, make_order):
    for _ in range(at_risk_threshold() + 2):
        make_order(status=OrderStatus.COMPLETED)

    assert admin_client.get(reverse(LIST_URL)).data["data"]["results"][0]["at_risk"] is False


@pytest.mark.django_db
def test_filters_by_active_state_search_and_at_risk(admin_client, customer_user, make_order):
    for _ in range(at_risk_threshold()):
        make_order(status=OrderStatus.NO_SHOW)

    assert admin_client.get(reverse(LIST_URL), {"at_risk": "true"}).data["data"]["count"] == 1
    assert admin_client.get(reverse(LIST_URL), {"at_risk": "false"}).data["data"]["count"] == 0
    assert admin_client.get(reverse(LIST_URL), {"is_active": "true"}).data["data"]["count"] == 1
    assert admin_client.get(reverse(LIST_URL), {"is_active": "false"}).data["data"]["count"] == 0
    assert admin_client.get(reverse(LIST_URL), {"q": "test customer"}).data["data"]["count"] == 1
    assert admin_client.get(reverse(LIST_URL), {"q": "0901234567"}).data["data"]["count"] == 1
    assert admin_client.get(reverse(LIST_URL), {"q": "nobody"}).data["data"]["count"] == 0


@pytest.mark.django_db
def test_an_admin_account_is_not_listed_as_a_customer(admin_client, admin_user, customer_user):
    rows = admin_client.get(reverse(LIST_URL)).data["data"]["results"]

    assert [row["id"] for row in rows] == [customer_user.id]


@pytest.mark.django_db
def test_the_impact_dialog_counts_open_orders_and_farmers(
    admin_client, customer_user, make_order
):
    make_order(status=OrderStatus.PLACED)
    make_order(status=OrderStatus.ACCEPTED)
    make_order(status=OrderStatus.READY_FOR_PICKUP)
    make_order(status=OrderStatus.CANCELLED)

    data = admin_client.get(reverse(IMPACT_URL, args=[customer_user.id])).data["data"]

    assert data["open_orders"] == {
        "PLACED": 1,
        "ACCEPTED": 1,
        "READY_FOR_PICKUP": 1,
        "total": 3,
    }
    assert data["affected_farmers"] == 1


@pytest.mark.django_db
def test_locking_cancels_every_open_order_and_restores_stock(
    admin_client, customer_user, product, make_order
):
    # D-015 / §5.4: T5, T6 and T13 all land on CANCELLED, but only the orders that actually
    # took stock give it back - D-029 means a PLACED order never deducted any.
    placed = make_order(status=OrderStatus.PLACED, quantity=2)
    accepted = make_order(status=OrderStatus.ACCEPTED, quantity=3)
    ready = make_order(status=OrderStatus.READY_FOR_PICKUP, quantity=1)
    completed = make_order(status=OrderStatus.COMPLETED, quantity=5)
    stock_before = product.stock_quantity

    response = admin_client.post(
        reverse(DEACTIVATE_URL, args=[customer_user.id]), {"reason": REASON}, format="json"
    )

    assert response.status_code == 200
    assert response.data["data"]["is_active"] is False
    assert response.data["data"]["deactivation_reason"] == REASON
    assert response.data["data"]["affected_orders"] == 3

    for order in (placed, accepted, ready):
        order.refresh_from_db()
        assert order.status == OrderStatus.CANCELLED
    completed.refresh_from_db()
    assert completed.status == OrderStatus.COMPLETED

    product.refresh_from_db()
    # Only the ACCEPTED (3) and READY_FOR_PICKUP (1) orders held stock; the PLACED one did not.
    assert product.stock_quantity == stock_before + 3 + 1


@pytest.mark.django_db
def test_locking_writes_the_admin_change_reason(admin_client, customer_user, make_order, admin_user):
    ready = make_order(status=OrderStatus.READY_FOR_PICKUP)

    admin_client.post(
        reverse(DEACTIVATE_URL, args=[customer_user.id]), {"reason": REASON}, format="json"
    )

    row = OrderStatusHistory.objects.get(order=ready)
    assert row.to_status == OrderStatus.CANCELLED
    # READY_FOR_PICKUP -> CANCELLED is T13, reserved for an admin.
    assert row.transition == Transition.T13
    assert row.actor_role == "ADMIN"
    assert row.actor == admin_user
    assert row.change_reason == ChangeReason.CUSTOMER_LOCKED_BY_ADMIN


@pytest.mark.django_db
def test_locking_tells_the_farmer_to_sell_the_goods(admin_client, customer_user, make_order, farmer_user):
    make_order(status=OrderStatus.PLACED)

    admin_client.post(
        reverse(DEACTIVATE_URL, args=[customer_user.id]), {"reason": REASON}, format="json"
    )

    assert Notification.objects.filter(
        recipient=farmer_user, type=NotificationType.ORDER_CANCELLED_CUSTOMER_LOCKED
    ).exists()


@pytest.mark.django_db
def test_locking_requires_a_reason(admin_client, customer_user):
    for body in ({}, {"reason": "no"}):
        response = admin_client.post(
            reverse(DEACTIVATE_URL, args=[customer_user.id]), body, format="json"
        )
        assert response.status_code == 400
        assert "reason" in response.data["errors"]

    customer_user.refresh_from_db()
    assert customer_user.is_active is True


@pytest.mark.django_db
def test_locking_audits_the_reason_and_the_order_count(
    admin_client, customer_user, make_order, admin_user
):
    make_order(status=OrderStatus.PLACED)

    admin_client.post(
        reverse(DEACTIVATE_URL, args=[customer_user.id]), {"reason": REASON}, format="json"
    )

    entry = AuditLog.objects.get(action=AuditAction.CUSTOMER_DEACTIVATED)
    assert entry.user == admin_user
    assert entry.details["customer_id"] == customer_user.id
    assert entry.details["reason"] == REASON
    assert entry.details["affected_orders"] == 1


@pytest.mark.django_db
def test_locking_an_already_locked_account_is_refused(admin_client, customer_user):
    admin_client.post(
        reverse(DEACTIVATE_URL, args=[customer_user.id]), {"reason": REASON}, format="json"
    )

    response = admin_client.post(
        reverse(DEACTIVATE_URL, args=[customer_user.id]), {"reason": REASON}, format="json"
    )

    assert response.status_code == 400
    assert response.data["code"] == "INVALID_STATUS_TRANSITION"


@pytest.mark.django_db
def test_unlocking_clears_the_reason(admin_client, customer_user, admin_user):
    admin_client.post(
        reverse(DEACTIVATE_URL, args=[customer_user.id]), {"reason": REASON}, format="json"
    )

    response = admin_client.post(reverse(ACTIVATE_URL, args=[customer_user.id]))

    assert response.status_code == 200
    assert response.data["data"]["is_active"] is True
    # D-024: the reason goes back to NULL when the account is unlocked.
    assert response.data["data"]["deactivation_reason"] is None
    customer_user.refresh_from_db()
    assert customer_user.is_active is True
    assert AuditLog.objects.filter(action=AuditAction.CUSTOMER_ACTIVATED).count() == 1


@pytest.mark.django_db
def test_unlocking_an_active_account_is_refused(admin_client, customer_user):
    response = admin_client.post(reverse(ACTIVATE_URL, args=[customer_user.id]))

    assert response.status_code == 400
    assert response.data["code"] == "INVALID_STATUS_TRANSITION"


@pytest.mark.django_db
def test_the_detail_adds_the_address_and_recent_orders(admin_client, customer_user, make_order):
    newest = make_order(status=OrderStatus.PLACED)
    make_order(status=OrderStatus.COMPLETED, created_days_ago=5)

    data = admin_client.get(reverse(DETAIL_URL, args=[customer_user.id])).data["data"]

    assert data["address"] == "12 Test Street"
    assert len(data["recent_orders"]) == 2
    assert data["recent_orders"][0]["id"] == newest.id
    assert data["recent_orders"][0]["total_amount"] == "5.00"


@pytest.mark.django_db
def test_recent_orders_are_capped_at_ten(admin_client, customer_user, make_order):
    for index in range(12):
        make_order(status=OrderStatus.COMPLETED, created_days_ago=index)

    data = admin_client.get(reverse(DETAIL_URL, args=[customer_user.id])).data["data"]

    assert len(data["recent_orders"]) == 10


@pytest.mark.django_db
def test_an_unknown_customer_is_a_404(admin_client):
    assert admin_client.get(reverse(DETAIL_URL, args=[9999])).status_code == 404
    assert admin_client.get(reverse(IMPACT_URL, args=[9999])).status_code == 404
    assert admin_client.post(reverse(ACTIVATE_URL, args=[9999])).status_code == 404


@pytest.mark.django_db
def test_a_farmer_id_is_not_a_customer_id(admin_client, approved_farmer):
    # The two profiles share the users table, so the route must not accept a farmer here.
    assert admin_client.get(reverse(DETAIL_URL, args=[approved_farmer.user_id])).status_code == 404


@pytest.mark.django_db
def test_customer_cannot_reach_the_customer_admin(customer_client, customer_user):
    assert customer_client.get(reverse(LIST_URL)).status_code == 403
    assert (
        customer_client.post(
            reverse(DEACTIVATE_URL, args=[customer_user.id]), {"reason": REASON}, format="json"
        ).status_code
        == 403
    )


@pytest.mark.django_db
def test_locking_clears_any_pending_change_request(admin_client, customer_user, make_order):
    # §5.4 step 4: the request dies with the order it belonged to.
    order = make_order(status=OrderStatus.ACCEPTED)
    Order.objects.filter(pk=order.pk).update(pending_change={"items": []})

    admin_client.post(
        reverse(DEACTIVATE_URL, args=[customer_user.id]), {"reason": REASON}, format="json"
    )

    order.refresh_from_db()
    assert order.pending_change is None
    assert order.status == OrderStatus.CANCELLED


@pytest.mark.django_db
def test_customers_sort_by_name_and_reject_unknown_columns(admin_client, customer_user):
    names = lambda ordering: [  # noqa: E731
        row["full_name"]
        for row in admin_client.get(reverse(LIST_URL), {"ordering": ordering})
        .data["data"]["results"]
    ]

    assert names("full_name") == sorted(names("full_name"))
    assert names("-full_name") == sorted(names("full_name"), reverse=True)

    refused = admin_client.get(reverse(LIST_URL), {"ordering": "user__password"})
    assert refused.status_code == 400
    assert "ordering" in refused.data["errors"]


@pytest.mark.django_db
def test_the_default_still_floats_at_risk_customers_to_the_top(admin_client, customer_user):
    # D-028 wanted this before sorting existed, so it stays the default rather than becoming
    # just another sort key.
    response = admin_client.get(reverse(LIST_URL))

    assert response.status_code == 200
    rows = response.data["data"]["results"]
    assert [row["at_risk"] for row in rows] == sorted(
        (row["at_risk"] for row in rows), reverse=True
    )


@pytest.mark.django_db
def test_admin_corrects_a_shoppers_details(admin_client, customer_user, admin_user):
    profile = customer_user.customer_profile

    response = admin_client.patch(
        reverse(DETAIL_URL, args=[profile.user_id]),
        {"full_name": "Linh Pham", "address": "99 New Street"},
        format="json",
    )

    assert response.status_code == 200
    profile.refresh_from_db()
    assert profile.full_name == "Linh Pham"
    assert profile.address == "99 New Street"

    entry = AuditLog.objects.get(action=AuditAction.CUSTOMER_UPDATED)
    assert entry.user == admin_user
    assert sorted(entry.details["changed_fields"]) == ["address", "full_name"]


@pytest.mark.django_db
def test_a_shoppers_phone_may_match_a_stall(admin_client, customer_user, farmer_user):
    stall_phone = farmer_user.farmer_profile.phone

    response = admin_client.patch(
        reverse(DETAIL_URL, args=[customer_user.customer_profile.user_id]),
        {"phone": stall_phone},
        format="json",
    )

    # customer_profiles and farmer_profiles carry their own UNIQUE index, and registration
    # checks only within a role; the admin edit follows the same rule.
    assert response.status_code == 200


@pytest.mark.django_db
def test_the_edit_cannot_reach_the_lock_reason(admin_client, customer_user):
    profile = customer_user.customer_profile

    admin_client.patch(
        reverse(DETAIL_URL, args=[profile.user_id]),
        {"deactivation_reason": "made up"},
        format="json",
    )

    profile.refresh_from_db()
    # The lock reason is written by AD-12 and cleared by AD-13; an edit form must not forge it.
    assert profile.deactivation_reason is None
