"""Admin moderation of a product listing.

Two actions, deliberately separate (AD-21, AD-21b):

* **Hide** is an investigation. The listing goes dark and nothing else moves; every order
  already placed against it stands, because the admin does not yet know there is a problem.
* **Block** is a takedown. The listing goes dark *and* every open order containing it is
  declined and restocked, because the item must not change hands at all.

Both write the same `is_hidden_by_admin` flag, so no public query has to know this file
exists; `moderation_action` records which of the two happened, and therefore whether the way
back is Restore or Unblock. Neither ever deletes a row (D-016 / D-017).
"""

from django.db import transaction
from django.db.models import Count
from django.utils import timezone

from catalog.models import ModerationAction, Product
from notifications.models import NotificationType
from notifications.services import notify
from orders.admin_selectors import open_order_breakdown
from orders.models import OPEN_STATUSES, ActorRole, ChangeReason, Order, OrderStatus
from orders.services.fsm import transition_order


def _open_orders_for(product_id: int):
    return Order.objects.filter(items__product_id=product_id, status__in=OPEN_STATUSES)


def _mark_hidden(product: Product, *, action: str, reason: str, actor) -> None:
    product.is_hidden_by_admin = True
    product.moderation_action = action
    product.hidden_reason = reason
    product.hidden_at = timezone.now()
    product.hidden_by = actor
    product.save(
        update_fields=[
            "is_hidden_by_admin",
            "moderation_action",
            "hidden_reason",
            "hidden_at",
            "hidden_by",
            "updated_at",
        ]
    )


def _clear_hidden(product: Product) -> None:
    product.is_hidden_by_admin = False
    product.moderation_action = None
    product.hidden_reason = None
    product.hidden_at = None
    product.hidden_by = None
    product.save(
        update_fields=[
            "is_hidden_by_admin",
            "moderation_action",
            "hidden_reason",
            "hidden_at",
            "hidden_by",
            "updated_at",
        ]
    )


# Both actions are idempotent: AD-21 lists no error code, so re-hiding just updates the reason.
@transaction.atomic
def hide_product(*, product_id: int, reason: str, actor) -> Product:
    product = Product.objects.select_for_update().get(pk=product_id)
    _mark_hidden(product, action=ModerationAction.HIDE, reason=reason, actor=actor)
    return product


@transaction.atomic
def restore_product(*, product_id: int) -> Product:
    product = Product.objects.select_for_update().get(pk=product_id)
    _clear_hidden(product)
    return product


def block_impact(*, product_id: int) -> dict:
    """What a block would cost, for the confirmation dialog (same shape as AD-04)."""
    orders = _open_orders_for(product_id)
    return {
        "open_orders": open_order_breakdown(Order.objects.filter(items__product_id=product_id)),
        "affected_customers": orders.values("customer_id").distinct().count(),
    }


@transaction.atomic
def block_product(*, product_id: int, reason: str, actor) -> tuple[Product, list[int]]:
    """Hide the listing and decline every open order that contains it.

    The whole order goes, not just the offending line. Removing one `order_items` row would
    leave `total_amount` disagreeing with the sum of the lines, which silently corrupts the
    AD-25 revenue report; and a shopper who came for three things should not be handed two
    without being asked.
    """
    product = Product.objects.select_for_update().get(pk=product_id)

    # Materialised and sorted by id before any of them is touched, which is the lock order
    # the rest of the codebase uses (orders, then products) and what keeps two admins acting
    # on overlapping orders from deadlocking.
    order_ids = list(_open_orders_for(product_id).order_by("id").values_list("id", flat=True))
    # A change request dies with the order it belonged to, as in the market closure cascade.
    Order.objects.filter(pk__in=order_ids).exclude(pending_change=None).update(pending_change=None)
    for order_id in order_ids:
        # No new transition code: DECLINED from any open status already exists and already
        # admits ADMIN (T3, T4, T12). Only the stamped reason differs from a suspension,
        # which is why transition_order takes one.
        transition_order(
            order_id=order_id,
            to_status=OrderStatus.DECLINED,
            actor=actor,
            actor_role=ActorRole.ADMIN,
            admin_change_reason=ChangeReason.PRODUCT_BLOCKED_BY_ADMIN,
        )

    _mark_hidden(product, action=ModerationAction.BLOCK, reason=reason, actor=actor)
    notify(
        recipient=product.farmer.user,
        event_type=NotificationType.PRODUCT_BLOCKED,
        context={
            "product_name": product.name,
            "order_count": len(order_ids),
            "reason": reason,
        },
    )
    # The ids, not just how many: a takedown cancels other people's orders, and six months
    # later the only way to answer "why was my order cancelled" is to find this row and read
    # which orders it named.
    return product, order_ids


@transaction.atomic
def unblock_product(*, product_id: int) -> Product:
    """Put the listing back on sale.

    It does **not** revive the orders the block declined: those shoppers have been told their
    order is off and may well have bought elsewhere. The screen says so before the admin
    confirms, because an Unblock button that looks like an undo is worse than no button.
    """
    product = Product.objects.select_for_update().get(pk=product_id)
    _clear_hidden(product)
    return product


def open_order_counts(*, product_ids) -> dict[int, int]:
    """How many open orders each product sits in, for the moderation list.

    A separate query rather than another annotate on the product list: that list already
    aggregates over `order_items` for the rating, and a second multi-valued join through the
    same path would multiply the rows and corrupt the average.
    """
    ids = list(product_ids)
    if not ids:
        return {}
    rows = (
        Order.objects.filter(items__product_id__in=ids, status__in=OPEN_STATUSES)
        .values("items__product_id")
        .annotate(total=Count("id", distinct=True))
        .values_list("items__product_id", "total")
    )
    return dict(rows)
