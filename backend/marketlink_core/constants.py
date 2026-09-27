"""Operating limits.

Read from the environment so they can be changed without a code edit, with the documented
default as the fallback. The admin Settings screen shows what is actually in force.
"""

import os


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


# U-01: D-013 says "the next N days"; the resolved value is 7.
# Bounds how far ahead a customer may book a pickup, and therefore which market and
# farmer closures count as "upcoming" in MarketSummary and FarmerSummary (D-023).
BOOKING_HORIZON_DAYS = _int_env("BOOKING_HORIZON_DAYS", 7)

# Image upload ceiling shown to the frontend (PU-01) and enforced on every upload field.
MAX_UPLOAD_MB = _int_env("MAX_UPLOAD_MB", 2)

# D-005 cap on unapproved PLACED orders per customer.
MAX_PLACED_ORDERS_PER_CUSTOMER = _int_env("MAX_PLACED_ORDERS_PER_CUSTOMER", 10)
