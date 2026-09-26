import ipaddress
import uuid

from rest_framework.settings import api_settings

from marketlink_core.exceptions import BusinessValidationError, ErrorCode, PreconditionRequiredError


# request_id columns are CHAR(36), so anything that is not a UUID must be dropped.
def normalize_request_id(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        return str(uuid.UUID(raw.strip()))
    except (ValueError, AttributeError):
        return None


def client_ip(request) -> str | None:
    """The client IP by the same rule as DRF's throttle ident (NUM_PROXIES).

    X-Forwarded-For is only trusted for the entry appended by our own proxies; the first
    entry is whatever the client sent and must never be used.
    """
    candidate = request.META.get("REMOTE_ADDR") or ""
    num_proxies = api_settings.NUM_PROXIES
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if num_proxies and forwarded:
        addresses = forwarded.split(",")
        candidate = addresses[-min(num_proxies, len(addresses))].strip()
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None


def parse_if_match(request) -> int:
    raw = request.headers.get("If-Match")
    if raw is None or not raw.strip():
        raise PreconditionRequiredError(
            "The If-Match header is required.", code=ErrorCode.PRECONDITION_REQUIRED
        )
    cleaned = raw.strip().removeprefix("W/").strip().strip('"').strip("'")
    try:
        version = int(cleaned)
    except ValueError:
        version = 0
    if version < 1:
        raise BusinessValidationError(
            "Invalid If-Match value.",
            code=ErrorCode.VALIDATION_ERROR,
            errors={"if_match": ["Invalid If-Match value."]},
        )
    return version


def require_idempotency_key(request) -> str:
    """Read the Idempotency-Key header of CU-04 (Pass 4B §1.2): a UUID, required."""
    raw = request.headers.get("Idempotency-Key")
    if raw is None or not raw.strip():
        raise PreconditionRequiredError(
            "The Idempotency-Key header is required.",
            code=ErrorCode.PRECONDITION_REQUIRED,
            errors={"idempotency_key": ["The Idempotency-Key header is required."]},
        )
    try:
        return str(uuid.UUID(raw.strip()))
    except ValueError as exc:
        raise BusinessValidationError(
            "Invalid Idempotency-Key value.",
            code=ErrorCode.VALIDATION_ERROR,
            errors={"idempotency_key": ["Idempotency-Key must be a UUID."]},
        ) from exc
