"""D-032: look up farmer coordinates from an address with OpenStreetMap Nominatim.

Rules: call outside any DB transaction, timeout 5 s, at most 1 request per second, own
User-Agent. Any failure returns None so registration / profile updates never break.
"""

import json
import logging
import time
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger("marketlink")

TIMEOUT_SECONDS = 5
# Nominatim usage policy: max 1 request per second for the whole app (shared via the cache).
RATE_LIMIT_KEY = "geocoding:nominatim:slot"
RATE_LIMIT_WINDOW_SECONDS = 1
RATE_LIMIT_MAX_WAIT_SECONDS = 2
COORDINATE_STEP = Decimal("0.000001")  # DecimalField(max_digits=9, decimal_places=6)


def geocode_address(address: str | None) -> tuple[Decimal, Decimal] | None:
    """Return (latitude, longitude) rounded to 6 decimals, or None when not found / failed."""
    if not getattr(settings, "GEOCODING_ENABLED", True):
        return None
    query = (address or "").strip()
    if not query:
        return None
    if not _acquire_rate_slot():
        logger.warning("Geocoding skipped: Nominatim rate limit slot not available")
        return None

    params = urlencode({"q": query, "format": "jsonv2", "limit": 1, "countrycodes": "vn"})
    request = Request(
        f"{settings.NOMINATIM_URL}?{params}",
        headers={"User-Agent": settings.NOMINATIM_USER_AGENT, "Accept-Language": "en"},
    )
    try:
        with urlopen(request, timeout=TIMEOUT_SECONDS) as response:  # noqa: S310 - fixed https URL from settings
            results = json.loads(response.read().decode("utf-8"))
    except (OSError, ValueError):  # URLError, timeouts and bad JSON; the address is not logged
        logger.warning("Geocoding request failed", exc_info=True)
        return None
    return _parse_first_result(results)


def _parse_first_result(results: object) -> tuple[Decimal, Decimal] | None:
    if not isinstance(results, list) or not results or not isinstance(results[0], dict):
        return None
    try:
        latitude = Decimal(str(results[0]["lat"])).quantize(COORDINATE_STEP, rounding=ROUND_HALF_UP)
        longitude = Decimal(str(results[0]["lon"])).quantize(COORDINATE_STEP, rounding=ROUND_HALF_UP)
    except (KeyError, InvalidOperation):
        return None
    if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
        return None
    return latitude, longitude


def _acquire_rate_slot() -> bool:
    deadline = time.monotonic() + RATE_LIMIT_MAX_WAIT_SECONDS
    while True:
        if cache.add(RATE_LIMIT_KEY, 1, timeout=RATE_LIMIT_WINDOW_SECONDS):
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.2)
