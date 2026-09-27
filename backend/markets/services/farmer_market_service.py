"""Attaching a stall to a market.

A stall trades at exactly one market. Moving to another one is a fresh registration, not an
edit, which is why this is the only way a `FarmerMarket` row should ever be created: the rule
has to hold whichever side of the app asks for the link.

The database carries the same rule as a unique index on the farmer column, so a caller that
forgets this function still cannot create a second one. This layer exists to turn that into a
sentence an admin can read instead of an integrity error.
"""

from django.db import transaction

from accounts.models import FarmerProfile
from marketlink_core.exceptions import BusinessValidationError, ErrorCode
from markets.models import FarmerMarket, Market


def current_market(*, farmer_id: int) -> FarmerMarket | None:
    return FarmerMarket.objects.select_related("market").filter(farmer_id=farmer_id).first()


@transaction.atomic
def link_stall_to_market(*, farmer_id: int, market_id: int, stall_label: str) -> FarmerMarket:
    """Register a stall at a market, or refuse because it already has one."""
    existing = (
        FarmerMarket.objects.select_for_update()
        .select_related("market")
        .filter(farmer_id=farmer_id)
        .first()
    )
    if existing is not None:
        if existing.market_id == market_id:
            return existing
        raise BusinessValidationError(
            f"This stall is already registered at {existing.market.name}.",
            code=ErrorCode.RESOURCE_IN_USE,
            errors={
                "market_id": [
                    "A stall trades at one market. Remove the current registration before "
                    "registering at another one."
                ]
            },
        )
    farmer = FarmerProfile.objects.get(pk=farmer_id)
    market = Market.objects.get(pk=market_id)
    return FarmerMarket.objects.create(
        farmer=farmer, market=market, stall_label=stall_label
    )
