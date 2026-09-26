import json
import logging
import uuid
from typing import Any

from django.conf import settings
from django.core.cache import cache
from redis.exceptions import RedisError

logger = logging.getLogger("marketlink")

TICKET_PREFIX = "ws_ticket:"
DEFAULT_TTL = getattr(settings, "WS_TICKET_TTL", 30)


def _use_redis() -> bool:
    return bool(getattr(settings, "USE_REDIS", False))


def _redis():
    """Raw redis-py client: the django-redis cache API has no GETDEL."""
    from django_redis import get_redis_connection

    return get_redis_connection("default")


def _parse_ticket(ticket: Any) -> str | None:
    """Only well-formed UUIDs reach the cache, so junk query strings cost no Redis command."""
    if not isinstance(ticket, str):
        return None
    try:
        return str(uuid.UUID(ticket.strip()))
    except ValueError:
        return None


def _decode(raw: Any) -> dict[str, Any] | None:
    if isinstance(raw, dict):
        payload = raw
    elif isinstance(raw, (bytes, str)):
        try:
            payload = json.loads(raw)
        except ValueError:
            return None
    else:
        return None
    return payload if isinstance(payload, dict) and "user_id" in payload else None


def create_ws_ticket(*, user_id: int, role: str, session_id: str | None = None) -> str:
    """AU-08: store a single-use ticket for WS_TICKET_TTL seconds and return it.

    session_id (the JWT "sid") lets a logout close the sockets of that one device only.
    """
    ticket = str(uuid.uuid4())
    key = f"{TICKET_PREFIX}{ticket}"
    payload: dict[str, Any] = {"user_id": user_id, "role": role}
    if session_id:
        payload["sid"] = session_id
    if _use_redis():
        _redis().set(key, json.dumps(payload), ex=DEFAULT_TTL)
    else:
        cache.set(key, payload, timeout=DEFAULT_TTL)
    return ticket


def verify_and_consume_ws_ticket(*, ticket: Any) -> dict[str, Any] | None:
    """Return the ticket payload once; any later call with the same ticket returns None (CT-16)."""
    parsed = _parse_ticket(ticket)
    if parsed is None:
        return None
    key = f"{TICKET_PREFIX}{parsed}"

    if _use_redis():
        try:
            # One atomic command (Redis >= 6.2): read and delete together, so a ticket
            # can never be used by two connections.
            raw = _redis().getdel(key)
        except RedisError:
            logger.exception("WebSocket ticket lookup failed")
            return None  # fail closed: the consumer closes with 4401
        return _decode(raw)

    # LocMem fallback (dev in one process, tests): accept only if this call removed the key.
    raw = cache.get(key)
    if raw is None or not cache.delete(key):
        return None
    return _decode(raw)
