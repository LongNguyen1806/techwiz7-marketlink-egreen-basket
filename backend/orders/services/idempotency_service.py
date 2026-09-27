import hashlib
import json
import logging
import uuid
from dataclasses import dataclass

from django.core.cache import cache

from orders.exceptions import IdempotencyInProgressError, IdempotencyKeyReusedError

logger = logging.getLogger(__name__)

# Pass 4B §5.1 step 1. Needs a shared cache (Redis, USE_REDIS=True) when running more than one worker.
# The processing claim must outlive a checkout that waits on several row locks (up to 50 s each) and one
# deadlock retry. If a worker dies mid-request the key stays "in progress" for this long; a duplicate
# order is still impossible afterwards because D-005 allows one open order per farmer.
PROCESSING_TTL_SECONDS = 5 * 60
RESULT_TTL_SECONDS = 24 * 60 * 60


@dataclass(frozen=True)
class IdempotentResult:
    status: int
    body: dict
    replayed: bool


def _cache_key(user_id, key: str) -> str:
    return f"idem:{user_id}:{key}"


def fingerprint(payload) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()


def _claim(*, user_id, key: str, request_hash: str) -> tuple[str | None, dict | None]:
    """Returns (token, None) when this request owns the key, or (None, entry) to replay a finished one."""
    cache_key = _cache_key(user_id, key)
    token = uuid.uuid4().hex
    for _ in range(2):
        if cache.add(cache_key, {"state": "processing", "hash": request_hash, "token": token}, timeout=PROCESSING_TTL_SECONDS):
            return token, None
        entry = cache.get(cache_key)
        if entry is None:
            continue  # freed between add() and get(); try to claim it once more
        if entry["hash"] != request_hash:
            raise IdempotencyKeyReusedError()
        if entry["state"] == "processing":
            raise IdempotencyInProgressError()
        return None, entry
    raise IdempotencyInProgressError()


def _release(cache_key: str, token: str) -> None:
    """Best effort: a cache failure here must not hide the business error that is being raised."""
    try:
        entry = cache.get(cache_key)
        if entry is not None and entry.get("token") == token:
            cache.delete(cache_key)
    except Exception:
        logger.warning("Could not release idempotency key %s", cache_key, exc_info=True)


def run_idempotent(*, user_id, key: str, payload, action) -> IdempotentResult:
    request_hash = fingerprint(payload)
    cache_key = _cache_key(user_id, key)
    token, stored = _claim(user_id=user_id, key=key, request_hash=request_hash)
    if stored is not None:
        return IdempotentResult(status=stored["status"], body=stored["body"], replayed=True)
    try:
        status, body = action()
    except BaseException:
        _release(cache_key, token)
        raise
    try:
        cache.set(cache_key, {"state": "done", "hash": request_hash, "status": status, "body": body}, timeout=RESULT_TTL_SECONDS)
    except Exception:
        # The orders are already committed; losing the replay copy must not turn their 201 into a 500.
        logger.warning("Could not store idempotent response for %s", cache_key, exc_info=True)
    return IdempotentResult(status=status, body=body, replayed=False)
