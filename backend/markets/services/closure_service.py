from datetime import date

from django.db import transaction

from marketlink_core.exceptions import (
    BusinessValidationError,
    ErrorCode,
    UnprocessableEntityError,
)
from markets.models import Market, MarketClosure
from orders.models import OPEN_STATUSES

MAX_REPORTED_ORDER_IDS = 20


@transaction.atomic
def create_closure(
    *, market_id: int, start_date: date, end_date: date, reason: str | None
) -> MarketClosure:
    market = Market.objects.select_for_update().get(pk=market_id)

    overlapping = MarketClosure.objects.filter(
        market=market, start_date__lte=end_date, end_date__gte=start_date
    ).first()
    if overlapping is not None:
        raise BusinessValidationError(
            "This period overlaps an existing closure "
            f"({overlapping.start_date} to {overlapping.end_date}).",
            errors={"start_date": ["This period overlaps an existing closure."]},
        )

    blocking_ids = list(
        market.orders.filter(
            status__in=OPEN_STATUSES, pickup_date__gte=start_date, pickup_date__lte=end_date
        )
        .order_by("id")
        .values_list("id", flat=True)[:MAX_REPORTED_ORDER_IDS]
    )
    if blocking_ids:
        raise UnprocessableEntityError(
            "Open orders are scheduled for pickup during this period.",
            code=ErrorCode.RESOURCE_IN_USE,
            errors={"order_ids": [str(order_id) for order_id in blocking_ids]},
        )

    return MarketClosure.objects.create(
        market=market, start_date=start_date, end_date=end_date, reason=reason
    )


def delete_closure(*, closure_id: int) -> None:
    MarketClosure.objects.filter(pk=closure_id).delete()
