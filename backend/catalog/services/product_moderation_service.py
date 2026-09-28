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

from marketlink_core.exceptions import BusinessValidationError, ErrorCode

from catalog.ai_review.service import record_admin_decision
from catalog.models import REVIEWABLE_FIELDS, ModerationAction, Product, ReviewStatus
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

    order_ids = list(_open_orders_for(product_id).order_by("id").values_list("id", flat=True))
    Order.objects.filter(pk__in=order_ids).exclude(pending_change=None).update(pending_change=None)
    for order_id in order_ids:
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


@transaction.atomic
def approve_product(*, product_id: int, actor) -> Product:
    product = Product.objects.select_for_update().select_related("farmer__user").get(pk=product_id)
    if product.review_status == ReviewStatus.APPROVED:
        raise BusinessValidationError(
            "This listing has already been approved.",
            code=ErrorCode.INVALID_STATUS_TRANSITION,
        )
    _set_review(product, status=ReviewStatus.APPROVED, note=None, actor=actor)
    notify(
        recipient=product.farmer.user,
        event_type=NotificationType.PRODUCT_APPROVED,
        context={"product_name": product.name},
    )
    return product


@transaction.atomic
def reject_product(*, product_id: int, reason: str, actor) -> Product:
    product = Product.objects.select_for_update().select_related("farmer__user").get(pk=product_id)
    _set_review(product, status=ReviewStatus.REJECTED, note=reason, actor=actor)
    notify(
        recipient=product.farmer.user,
        event_type=NotificationType.PRODUCT_REJECTED,
        context={"product_name": product.name, "reason": reason},
    )
    return product


def _set_review(product: Product, *, status: str, note: str | None, actor) -> None:
    product.review_status = status
    product.review_note = note
    product.reviewed_at = timezone.now()
    product.reviewed_by = actor
    product.save(
        update_fields=["review_status", "review_note", "reviewed_at", "reviewed_by", "updated_at"]
    )
    record_admin_decision(product.pk, status, actor)


def needs_review_again(product: Product, changed_fields) -> bool:
    """Whether an edit puts the listing back in the queue.

    Only the fields that describe *what the thing is* count. Price and stock are excluded on
    purpose: a stall that must wait for an admin before correcting its own stock will stop
    correcting it, and the stock figure is the one number the whole booking flow rests on.

    An APPROVED listing goes back to PENDING; a REJECTED one is resubmitted by fixing what the
    admin pointed out. A PENDING one is already in the queue.

    Called from whichever endpoint saves a stall's edit; kept here so both sides of the app
    apply the same rule rather than each deciding for itself.
    """
    if product.review_status == ReviewStatus.PENDING:
        return False
    return any(field in REVIEWABLE_FIELDS for field in changed_fields)


def send_back_for_review(product: Product) -> None:
    """Put an edited listing back in the queue until an admin looks at the new wording.

    While it waits it is off the shopper side (catalogue, detail, search, new orders and order
    edits all require APPROVED), because the row now holds the unreviewed wording. Orders
    already placed for it are untouched and keep moving through accept, ready and complete.
    """
    product.review_status = ReviewStatus.PENDING
    product.review_note = None
    product.reviewed_at = None
    product.reviewed_by = None
    product.save(
        update_fields=["review_status", "review_note", "reviewed_at", "reviewed_by", "updated_at"]
    )
