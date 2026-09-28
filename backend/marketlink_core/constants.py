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


BOOKING_HORIZON_DAYS = _int_env("BOOKING_HORIZON_DAYS", 7)

MAX_UPLOAD_MB = _int_env("MAX_UPLOAD_MB", 2)

MAX_PLACED_ORDERS_PER_CUSTOMER = _int_env("MAX_PLACED_ORDERS_PER_CUSTOMER", 10)
