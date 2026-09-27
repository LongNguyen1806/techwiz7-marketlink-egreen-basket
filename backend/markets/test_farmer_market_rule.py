"""A stall trades at exactly one market.

Two layers enforce it: a service that says so in words, and a unique index that holds even
when a caller forgets the service. Both are tested, because the second one is the only real
guarantee and the first one is the only readable error.
"""

import pytest
from django.db.utils import IntegrityError

from marketlink_core.exceptions import BusinessValidationError
from markets.models import FarmerMarket, Market
from markets.services.farmer_market_service import current_market, link_stall_to_market


@pytest.fixture
def other_market(db):
    return Market.objects.create(
        name="Cho Tan Dinh",
        address="Hai Ba Trung, District 1, Ho Chi Minh City",
        latitude="10.790000",
        longitude="106.690000",
        open_time="05:00",
        close_time="17:00",
    )


@pytest.mark.django_db
def test_a_stall_registers_at_a_market(market, approved_farmer):
    link = link_stall_to_market(
        farmer_id=approved_farmer.user_id, market_id=market.id, stall_label="Row A, Stall 3"
    )

    assert link.market_id == market.id
    assert current_market(farmer_id=approved_farmer.user_id).market_id == market.id


@pytest.mark.django_db
def test_registering_at_a_second_market_is_refused(market, other_market, approved_farmer):
    link_stall_to_market(
        farmer_id=approved_farmer.user_id, market_id=market.id, stall_label="Row A, Stall 3"
    )

    with pytest.raises(BusinessValidationError) as caught:
        link_stall_to_market(
            farmer_id=approved_farmer.user_id,
            market_id=other_market.id,
            stall_label="Row B, Stall 9",
        )

    # The message names where the stall already is, so the admin does not have to go looking.
    assert market.name in str(caught.value.detail)
    assert FarmerMarket.objects.filter(farmer=approved_farmer).count() == 1


@pytest.mark.django_db
def test_registering_again_at_the_same_market_is_not_an_error(market, approved_farmer):
    first = link_stall_to_market(
        farmer_id=approved_farmer.user_id, market_id=market.id, stall_label="Row A, Stall 3"
    )
    again = link_stall_to_market(
        farmer_id=approved_farmer.user_id, market_id=market.id, stall_label="Row A, Stall 3"
    )

    # Idempotent: a repeated registration is the same registration, not a second one.
    assert again.pk == first.pk
    assert FarmerMarket.objects.filter(farmer=approved_farmer).count() == 1


@pytest.mark.django_db
def test_the_database_refuses_a_second_market_even_without_the_service(
    market, other_market, approved_farmer
):
    # The rule has to survive a caller on another branch that writes the row directly.
    FarmerMarket.objects.create(
        farmer=approved_farmer, market=market, stall_label="Row A, Stall 3"
    )

    with pytest.raises(IntegrityError):
        FarmerMarket.objects.create(
            farmer=approved_farmer, market=other_market, stall_label="Row B, Stall 9"
        )


@pytest.mark.django_db
def test_two_stalls_may_share_a_market(market, approved_farmer, make_farmer):
    other_farmer = make_farmer(email="second@marketlink.test", stall_name="Second Stall")

    link_stall_to_market(
        farmer_id=approved_farmer.user_id, market_id=market.id, stall_label="Row A, Stall 3"
    )
    link_stall_to_market(
        farmer_id=other_farmer.user_id, market_id=market.id, stall_label="Row A, Stall 4"
    )

    # The index is on the farmer, not on the market: a market holds as many stalls as it likes.
    assert FarmerMarket.objects.filter(market=market).count() == 2
