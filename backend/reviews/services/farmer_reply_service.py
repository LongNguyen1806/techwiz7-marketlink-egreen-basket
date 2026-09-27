"""FA-29 / FA-30: the farmer replies once to a review (D-016)."""

from django.db import transaction
from django.utils import timezone

from accounts.models import FarmerProfile, FarmerStatus
from marketlink_core.exceptions import (
    ErrorCode,
    ForbiddenActionError,
    ResourceNotFoundError,
    UnprocessableEntityError,
)
from orders.services.fsm import run_with_retry_if_top_level
from reviews.models import FarmerReview, ProductReview
from reviews.selectors import TYPE_FARMER

REPLY_MAX_LENGTH = 500


def reply_to_review(*, review_type: str, review_id: int, farmer_id: int, reply: str) -> int:
    """Lock the review row, then check: ownership (404) -> suspended -> hidden -> already replied.

    Returns the review id; the caller reloads it with the relations the response needs.
    """
    if review_type == TYPE_FARMER:
        model, owner_filter = FarmerReview, {"order__farmer_id": farmer_id}
    else:
        model, owner_filter = ProductReview, {"order_item__product__farmer_id": farmer_id}

    def _execute() -> int:
        with transaction.atomic():
            review = model.objects.select_for_update(of=("self",)).filter(pk=review_id, **owner_filter).first()
            if review is None:
                raise ResourceNotFoundError("Review not found.", code=ErrorCode.NOT_FOUND)
            # D5 v1.8: a reply is public content, so a suspended stall cannot post one.
            if FarmerProfile.objects.filter(pk=farmer_id, status=FarmerStatus.SUSPENDED).exists():
                raise ForbiddenActionError(
                    "Your stall is suspended, so you cannot reply to reviews.",
                    code=ErrorCode.FARMER_SUSPENDED,
                )
            if review.is_hidden_by_admin:
                raise UnprocessableEntityError(
                    "This review was hidden by an administrator and cannot be replied to.",
                    code=ErrorCode.FAILED_PRECONDITION,
                )
            if review.reply is not None:
                raise UnprocessableEntityError(
                    "You have already replied to this review.", code=ErrorCode.REPLY_ALREADY_EXISTS
                )
            review.reply = reply
            review.replied_at = timezone.now()
            review.save(update_fields=["reply", "replied_at", "updated_at"])
            return review.pk

    return run_with_retry_if_top_level(_execute)
