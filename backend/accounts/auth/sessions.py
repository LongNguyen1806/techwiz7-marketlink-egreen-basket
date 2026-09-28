import logging

from django.core.cache import caches
from django_redis.exceptions import ConnectionInterrupted
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import TimeoutError as RedisTimeoutError
from rest_framework_simplejwt.settings import api_settings as jwt_settings

logger = logging.getLogger(__name__)

_REVOKED_SESSION = "auth:revoked_sid:{}"
_USED_REFRESH = "auth:used_jti:{}"
_PASSWORD_KEEPER = "auth:password_keeper:{}"

_OUTAGE_ERRORS = (ConnectionError, TimeoutError, RedisConnectionError, RedisTimeoutError, ConnectionInterrupted)


def _store():
    return caches["blacklist"]


def _refresh_lifetime_seconds() -> int:
    return int(jwt_settings.REFRESH_TOKEN_LIFETIME.total_seconds())


def revoke_session(session_id: str) -> None:
    """Ends a whole device session: every refresh token of it and its live access tokens.

    Errors propagate on purpose: a logout that could not be stored must not report success.
    """
    _store().set(_REVOKED_SESSION.format(session_id), True, timeout=_refresh_lifetime_seconds())


def is_session_revoked(session_id: str) -> bool:
    """Access path (every authenticated request): a Redis outage lets requests through instead of
    failing the whole API; the access token still expires within 15 minutes."""
    try:
        return _store().get(_REVOKED_SESSION.format(session_id)) is not None
    except _OUTAGE_ERRORS:
        logger.warning("Could not read revoked sessions from Redis", exc_info=True)
        return False


def session_state(user_id, session_id: str) -> tuple[bool, dict | None]:
    """Refresh path, one round trip: (is the session revoked?, password-change exemption of the user).

    Errors propagate, so no new tokens are minted while revocation state is unknown.
    """
    revoked_key, keeper_key = _REVOKED_SESSION.format(session_id), _PASSWORD_KEEPER.format(user_id)
    values = _store().get_many([revoked_key, keeper_key])
    return revoked_key in values, values.get(keeper_key)


def claim_refresh_token(jti: str, *, ttl_seconds: int) -> bool:
    """SET NX: True only for the first request presenting this refresh token, so it is single-use (CT-15)."""
    return _store().add(_USED_REFRESH.format(jti), True, timeout=max(ttl_seconds, 1))


def keep_session_on_password_change(user_id, *, session_id: str, old_version: str, new_version: str) -> None:
    """Lets the device that changed the password refresh once more across exactly that change (AU-07)."""
    _store().set(
        _PASSWORD_KEEPER.format(user_id),
        {"sid": session_id, "from": old_version, "to": new_version},
        timeout=_refresh_lifetime_seconds(),
    )
