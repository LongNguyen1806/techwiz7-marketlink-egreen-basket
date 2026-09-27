import pytest
from django.urls import reverse

from accounts.models import FarmerStatus
from catalog.models import ModerationAction, Product, Unit
from notifications.models import Notification, NotificationType
from orders.models import ActorRole, ChangeReason, OrderStatus, OrderStatusHistory
from system.models import AuditAction, AuditLog

LIST_URL_NAME = "admin-product-list"
HIDE_URL_NAME = "admin-product-hide"
RESTORE_URL_NAME = "admin-product-restore"


@pytest.mark.django_db
def test_list_is_paginated_and_names_the_farmer(admin_client, product, approved_farmer):
    response = admin_client.get(reverse(LIST_URL_NAME))

    assert response.status_code == 200
    data = response.data["data"]
    assert {"count", "page", "page_size", "total_pages", "results"} <= data.keys()
    row = data["results"][0]
    assert row["name"] == "Tomato"
    assert row["farmer"] == {"id": approved_farmer.pk, "stall_name": "Test Stall"}
    assert row["category"]["name"] == "Vegetables"
    # Money is a decimal string, never a float (D-020).
    assert row["price"] == "2.50"
    assert row["availability"] == "IN_STOCK"
    assert row["is_hidden_by_admin"] is False
    assert row["hidden_reason"] is None
    assert row["is_favorite"] is None


@pytest.mark.django_db
def test_out_of_stock_and_paused_products_report_their_availability(
    admin_client, category, approved_farmer
):
    Product.objects.create(
        farmer=approved_farmer,
        category=category,
        name="Sold out lettuce",
        price="1.00",
        unit=Unit.BUNCH,
        stock_quantity=0,
    )
    Product.objects.create(
        farmer=approved_farmer,
        category=category,
        name="Paused carrot",
        price="1.00",
        unit=Unit.KG,
        stock_quantity=5,
        is_available=False,
    )

    rows = {r["name"]: r for r in admin_client.get(reverse(LIST_URL_NAME)).data["data"]["results"]}

    assert rows["Sold out lettuce"]["availability"] == "OUT_OF_STOCK"
    assert rows["Paused carrot"]["availability"] == "UNAVAILABLE"


@pytest.mark.django_db
def test_a_product_of_a_suspended_farmer_is_unavailable(admin_client, product, approved_farmer):
    approved_farmer.status = FarmerStatus.SUSPENDED
    approved_farmer.save(update_fields=["status"])

    row = admin_client.get(reverse(LIST_URL_NAME)).data["data"]["results"][0]

    assert row["availability"] == "UNAVAILABLE"


@pytest.mark.django_db
def test_held_quantity_is_every_open_accepted_or_ready_order(
    admin_client, product, seller_market, make_order_with_item
):
    # D-029 v1.8: stock leaves the shelf when the farmer accepts, so held_quantity counts every
    # open ACCEPTED or READY order - including one already past its pickup time, whose goods
    # are still off the shelf.
    make_order_with_item(product=product, quantity=3, status=OrderStatus.ACCEPTED)
    make_order_with_item(product=product, quantity=2, status=OrderStatus.READY_FOR_PICKUP)
    make_order_with_item(
        product=product, quantity=7, status=OrderStatus.ACCEPTED, days_ahead=-2
    )
    # A finished order released its goods; a PLACED one never took any.
    make_order_with_item(product=product, quantity=4, status=OrderStatus.COMPLETED)
    make_order_with_item(product=product, quantity=5, status=OrderStatus.PLACED)

    row = admin_client.get(reverse(LIST_URL_NAME)).data["data"]["results"][0]

    assert row["held_quantity"] == 3 + 2 + 7


@pytest.mark.django_db
def test_pending_quantity_counts_orders_awaiting_the_farmer(
    admin_client, product, seller_market, make_order_with_item
):
    # pending_quantity is for reconciliation only: PLACED orders whose pickup is still ahead.
    make_order_with_item(product=product, quantity=5, status=OrderStatus.PLACED)
    make_order_with_item(product=product, quantity=3, status=OrderStatus.ACCEPTED)
    make_order_with_item(
        product=product, quantity=9, status=OrderStatus.PLACED, days_ahead=-2
    )

    row = admin_client.get(reverse(LIST_URL_NAME)).data["data"]["results"][0]

    assert row["pending_quantity"] == 5
    assert row["held_quantity"] == 3


@pytest.mark.django_db
def test_markets_list_only_the_days_with_an_active_slot(admin_client, product, seller_market):
    row = admin_client.get(reverse(LIST_URL_NAME)).data["data"]["results"][0]

    assert row["markets"] == [
        {"market_id": seller_market.id, "market_name": "Central Market", "days": [1]}
    ]


@pytest.mark.django_db
def test_search_matches_product_name_or_stall_name(admin_client, product):
    assert admin_client.get(reverse(LIST_URL_NAME), {"q": "tomato"}).data["data"]["count"] == 1
    assert admin_client.get(reverse(LIST_URL_NAME), {"q": "Test Stall"}).data["data"]["count"] == 1
    assert admin_client.get(reverse(LIST_URL_NAME), {"q": "nothing"}).data["data"]["count"] == 0


@pytest.mark.django_db
def test_filter_by_farmer_and_hidden_state(admin_client, product, approved_farmer):
    assert (
        admin_client.get(reverse(LIST_URL_NAME), {"farmer_id": approved_farmer.pk}).data["data"][
            "count"
        ]
        == 1
    )
    assert admin_client.get(reverse(LIST_URL_NAME), {"farmer_id": 9999}).data["data"]["count"] == 0
    assert admin_client.get(reverse(LIST_URL_NAME), {"is_hidden": "true"}).data["data"]["count"] == 0
    assert (
        admin_client.get(reverse(LIST_URL_NAME), {"is_hidden": "false"}).data["data"]["count"] == 1
    )


@pytest.mark.django_db
def test_hide_records_the_reason_the_actor_and_an_audit_row(admin_client, product, admin_user):
    response = admin_client.post(
        reverse(HIDE_URL_NAME, args=[product.id]), {"reason": "Misleading photo"}, format="json"
    )

    assert response.status_code == 200
    assert response.data["data"]["is_hidden_by_admin"] is True
    assert response.data["data"]["hidden_reason"] == "Misleading photo"
    # A hidden product is no longer publicly on sale (§3.3).
    assert response.data["data"]["availability"] == "UNAVAILABLE"

    product.refresh_from_db()
    assert product.hidden_by == admin_user
    assert product.hidden_at is not None

    entry = AuditLog.objects.get(action=AuditAction.PRODUCT_HIDDEN)
    assert entry.user == admin_user
    assert entry.details["product_id"] == product.id
    assert entry.details["reason"] == "Misleading photo"


@pytest.mark.django_db
def test_hide_requires_a_reason_of_at_least_five_characters(admin_client, product):
    for body in ({}, {"reason": "bad"}):
        response = admin_client.post(
            reverse(HIDE_URL_NAME, args=[product.id]), body, format="json"
        )
        assert response.status_code == 400
        assert "reason" in response.data["errors"]

    product.refresh_from_db()
    assert product.is_hidden_by_admin is False
    assert not AuditLog.objects.filter(action=AuditAction.PRODUCT_HIDDEN).exists()


@pytest.mark.django_db
def test_hiding_twice_just_replaces_the_reason(admin_client, product):
    admin_client.post(
        reverse(HIDE_URL_NAME, args=[product.id]), {"reason": "First reason"}, format="json"
    )
    response = admin_client.post(
        reverse(HIDE_URL_NAME, args=[product.id]), {"reason": "Second reason"}, format="json"
    )

    assert response.status_code == 200
    assert response.data["data"]["hidden_reason"] == "Second reason"


@pytest.mark.django_db
def test_restore_clears_the_reason_and_audits(admin_client, product, admin_user):
    admin_client.post(
        reverse(HIDE_URL_NAME, args=[product.id]), {"reason": "Misleading photo"}, format="json"
    )

    response = admin_client.post(reverse(RESTORE_URL_NAME, args=[product.id]))

    assert response.status_code == 200
    assert response.data["data"]["is_hidden_by_admin"] is False
    assert response.data["data"]["hidden_reason"] is None
    assert response.data["data"]["availability"] == "IN_STOCK"

    product.refresh_from_db()
    assert product.hidden_by is None
    assert product.hidden_at is None
    assert AuditLog.objects.filter(action=AuditAction.PRODUCT_RESTORED).count() == 1


@pytest.mark.django_db
def test_restore_needs_no_body(admin_client, product):
    assert admin_client.post(reverse(RESTORE_URL_NAME, args=[product.id])).status_code == 200


@pytest.mark.django_db
def test_hiding_never_deletes_the_row(admin_client, product):
    admin_client.post(
        reverse(HIDE_URL_NAME, args=[product.id]), {"reason": "Policy breach"}, format="json"
    )

    # D-017: moderation is a soft flag, so the product survives.
    assert Product.objects.filter(pk=product.id).exists()


@pytest.mark.django_db
def test_unknown_product_is_a_404(admin_client):
    assert (
        admin_client.post(
            reverse(HIDE_URL_NAME, args=[9999]), {"reason": "Nothing here"}, format="json"
        ).status_code
        == 404
    )
    assert admin_client.post(reverse(RESTORE_URL_NAME, args=[9999])).status_code == 404


@pytest.mark.django_db
def test_customer_cannot_reach_the_product_moderation(customer_client, product):
    assert customer_client.get(reverse(LIST_URL_NAME)).status_code == 403
    assert (
        customer_client.post(
            reverse(HIDE_URL_NAME, args=[product.id]), {"reason": "Not allowed"}, format="json"
        ).status_code
        == 403
    )


@pytest.mark.django_db
def test_products_sort_by_name_and_price(admin_client, product, category, approved_farmer):
    for name, price in (("Aubergine", "2.00"), ("Zucchini", "9.00")):
        Product.objects.create(
            farmer=approved_farmer, category=category, name=name,
            price=price, unit=Unit.KG, stock_quantity=5,
        )

    def column(ordering, key):
        response = admin_client.get(reverse(LIST_URL_NAME), {"ordering": ordering})
        return [row[key] for row in response.data["data"]["results"]]

    assert column("name", "name") == sorted(column("name", "name"))
    assert column("-name", "name") == sorted(column("name", "name"), reverse=True)
    prices = [float(value) for value in column("price", "price")]
    assert prices == sorted(prices)


@pytest.mark.django_db
def test_products_reject_an_unknown_sort_column(admin_client):
    assert admin_client.get(reverse(LIST_URL_NAME), {"ordering": "farmer__user__password"}).status_code == 400


@pytest.mark.django_db
def test_unrated_products_stay_at_the_bottom_either_way(
    admin_client, product, category, approved_farmer, make_order_with_item
):
    # rating is the one sort built from an expression rather than a column name, because NULL
    # has to sink in both directions - a product nobody has reviewed is not the worst rated.
    from reviews.models import ProductReview

    unrated = Product.objects.create(
        farmer=approved_farmer, category=category, name="Unreviewed",
        price="1.00", unit=Unit.KG, stock_quantity=1,
    )
    order = make_order_with_item(product=product, status=OrderStatus.COMPLETED)
    ProductReview.objects.create(order_item=order.items.first(), rating=4, comment="Good.")

    for ordering in ("rating", "-rating"):
        response = admin_client.get(reverse(LIST_URL_NAME), {"ordering": ordering})
        ids = [row["id"] for row in response.data["data"]["results"]]
        assert ids[-1] == unrated.id, f"{ordering} floated an unrated product"


# --------------------------------------------------------------------- AD-21b
# Block is the takedown: it hides the listing *and* kills the orders. Hide leaves the orders
# alone. The tests below are mostly about keeping those two apart.

IMPACT_URL_NAME = "admin-product-block-impact"
BLOCK_URL_NAME = "admin-product-block"
UNBLOCK_URL_NAME = "admin-product-unblock"


@pytest.mark.django_db
def test_hide_leaves_every_open_order_untouched(admin_client, product, make_order_with_item):
    placed = make_order_with_item(product=product, status=OrderStatus.PLACED)
    accepted = make_order_with_item(product=product, status=OrderStatus.ACCEPTED)

    admin_client.post(
        reverse(HIDE_URL_NAME, args=[product.id]),
        {"reason": "Checking the source"},
        format="json",
    )

    placed.refresh_from_db()
    accepted.refresh_from_db()
    assert placed.status == OrderStatus.PLACED
    assert accepted.status == OrderStatus.ACCEPTED
    product.refresh_from_db()
    assert product.moderation_action == ModerationAction.HIDE


@pytest.mark.django_db
def test_block_impact_counts_open_orders_and_distinct_customers(
    admin_client, product, make_order_with_item
):
    make_order_with_item(product=product, status=OrderStatus.PLACED)
    make_order_with_item(product=product, status=OrderStatus.ACCEPTED)
    make_order_with_item(product=product, status=OrderStatus.READY_FOR_PICKUP)
    # Finished and cancelled orders are nobody's problem any more.
    make_order_with_item(product=product, status=OrderStatus.COMPLETED)
    make_order_with_item(product=product, status=OrderStatus.CANCELLED)

    data = admin_client.get(reverse(IMPACT_URL_NAME, args=[product.id])).data["data"]

    assert data["open_orders"] == {
        "PLACED": 1,
        "ACCEPTED": 1,
        "READY_FOR_PICKUP": 1,
        "total": 3,
    }
    # The fixture uses one shopper for all of them.
    assert data["affected_customers"] == 1


@pytest.mark.django_db
def test_block_declines_open_orders_restocks_and_audits(
    admin_client, product, admin_user, make_order_with_item
):
    placed = make_order_with_item(product=product, quantity=4, status=OrderStatus.PLACED)
    accepted = make_order_with_item(product=product, quantity=6, status=OrderStatus.ACCEPTED)
    completed = make_order_with_item(product=product, quantity=9, status=OrderStatus.COMPLETED)
    before = Product.objects.get(pk=product.id).stock_quantity

    response = admin_client.post(
        reverse(BLOCK_URL_NAME, args=[product.id]),
        {"reason": "Sold without a licence"},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["data"]["affected_orders"] == 2
    assert response.data["data"]["moderation_action"] == ModerationAction.BLOCK

    placed.refresh_from_db()
    accepted.refresh_from_db()
    completed.refresh_from_db()
    assert placed.status == OrderStatus.DECLINED
    assert accepted.status == OrderStatus.DECLINED
    # A finished order is history; the takedown does not reach back into it.
    assert completed.status == OrderStatus.COMPLETED

    # D-029: only the ACCEPTED order had taken stock off the shelf, so only its 6 come back.
    product.refresh_from_db()
    assert product.stock_quantity == before + 6

    entry = AuditLog.objects.get(action=AuditAction.PRODUCT_BLOCKED)
    assert entry.user == admin_user
    assert entry.details["affected_orders"] == 2
    # Which orders died, so the row can answer a shopper asking why theirs was cancelled.
    assert entry.details["cancelled_order_ids"] == sorted([placed.id, accepted.id])
    assert completed.id not in entry.details["cancelled_order_ids"]


@pytest.mark.django_db
def test_block_stamps_the_takedown_reason_not_the_suspension_one(
    admin_client, product, make_order_with_item
):
    # The same DECLINED transitions serve a stall suspension and a product takedown. If the
    # reason were still picked from the transition code alone, this shopper would be told the
    # stall had been suspended, which never happened.
    order = make_order_with_item(product=product, status=OrderStatus.ACCEPTED)

    admin_client.post(
        reverse(BLOCK_URL_NAME, args=[product.id]),
        {"reason": "Legal takedown"},
        format="json",
    )

    row = OrderStatusHistory.objects.filter(order=order).latest("id")
    assert row.to_status == OrderStatus.DECLINED
    assert row.actor_role == ActorRole.ADMIN
    assert row.change_reason == ChangeReason.PRODUCT_BLOCKED_BY_ADMIN


@pytest.mark.django_db
def test_block_cancels_the_whole_order_not_just_the_blocked_line(
    admin_client, product, category, approved_farmer, make_order_with_item
):
    other = Product.objects.create(
        farmer=approved_farmer,
        category=category,
        name="Something else",
        price="3.00",
        unit=Unit.KG,
        stock_quantity=50,
    )
    order = make_order_with_item(product=product, quantity=2, status=OrderStatus.ACCEPTED)
    order.items.create(
        product=other,
        product_name=other.name,
        unit_price=other.price,
        unit=other.unit,
        quantity=5,
        line_total="15.00",
    )
    other_before = other.stock_quantity

    admin_client.post(
        reverse(BLOCK_URL_NAME, args=[product.id]),
        {"reason": "Legal takedown"},
        format="json",
    )

    order.refresh_from_db()
    assert order.status == OrderStatus.DECLINED
    # Both lines survive as a record, and the untouched product gets its stock back too,
    # because the order it belonged to is gone.
    assert order.items.count() == 2
    other.refresh_from_db()
    assert other.stock_quantity == other_before + 5


@pytest.mark.django_db
def test_block_notifies_the_stall(admin_client, product, approved_farmer, make_order_with_item):
    make_order_with_item(product=product, status=OrderStatus.PLACED)

    admin_client.post(
        reverse(BLOCK_URL_NAME, args=[product.id]),
        {"reason": "Legal takedown"},
        format="json",
    )

    note = Notification.objects.get(
        recipient=approved_farmer.user, type=NotificationType.PRODUCT_BLOCKED
    )
    assert product.name in note.title
    assert "Legal takedown" in note.message


@pytest.mark.django_db
def test_block_requires_a_reason(admin_client, product, make_order_with_item):
    order = make_order_with_item(product=product, status=OrderStatus.ACCEPTED)

    response = admin_client.post(
        reverse(BLOCK_URL_NAME, args=[product.id]), {"reason": "no"}, format="json"
    )

    assert response.status_code == 400
    assert "reason" in response.data["errors"]
    order.refresh_from_db()
    assert order.status == OrderStatus.ACCEPTED
    product.refresh_from_db()
    assert product.is_hidden_by_admin is False


@pytest.mark.django_db
def test_unblock_puts_it_back_on_sale_without_reviving_the_orders(
    admin_client, product, admin_user, make_order_with_item
):
    order = make_order_with_item(product=product, status=OrderStatus.ACCEPTED)
    admin_client.post(
        reverse(BLOCK_URL_NAME, args=[product.id]),
        {"reason": "Legal takedown"},
        format="json",
    )

    response = admin_client.post(reverse(UNBLOCK_URL_NAME, args=[product.id]))

    assert response.status_code == 200
    assert response.data["data"]["is_hidden_by_admin"] is False
    assert response.data["data"]["moderation_action"] is None
    assert response.data["data"]["hidden_reason"] is None

    # The whole point of the separate verb: this order stays dead.
    order.refresh_from_db()
    assert order.status == OrderStatus.DECLINED

    assert (
        AuditLog.objects.filter(action=AuditAction.PRODUCT_UNBLOCKED, user=admin_user).count() == 1
    )


@pytest.mark.django_db
def test_moderation_list_reports_the_action_and_the_open_order_count(
    admin_client, product, make_order_with_item
):
    make_order_with_item(product=product, status=OrderStatus.PLACED)
    make_order_with_item(product=product, status=OrderStatus.ACCEPTED)
    make_order_with_item(product=product, status=OrderStatus.COMPLETED)

    row = admin_client.get(reverse(LIST_URL_NAME)).data["data"]["results"][0]

    assert row["open_order_count"] == 2
    assert row["moderation_action"] is None
    # The rating average must survive the extra counting; it is aggregated over the same join.
    assert row["rating_count"] == 0


@pytest.mark.django_db
def test_customer_cannot_block_or_unblock(customer_client, product):
    for name in (IMPACT_URL_NAME, BLOCK_URL_NAME, UNBLOCK_URL_NAME):
        method = customer_client.get if name == IMPACT_URL_NAME else customer_client.post
        assert method(reverse(name, args=[product.id])).status_code == 403
