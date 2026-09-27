# The market and order fixtures live with the markets app. Importing them here lets pytest
# find them for these tests without moving shared fixtures that other apps already rely on.
from markets.conftest import (  # noqa: F401
    approved_farmer,
    farmer_market,
    make_order,
    market,
)
