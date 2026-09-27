import logging
from typing import Any

from django.core.exceptions import ObjectDoesNotExist
from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import ProtectedError, RestrictedError
from django.db.utils import DataError, IntegrityError, OperationalError
from django.http import Http404
from rest_framework.exceptions import (
    APIException,
    AuthenticationFailed,
    NotAuthenticated,
    NotFound,
    ParseError,
    Throttled,
)
from rest_framework.exceptions import PermissionDenied as DRFPermissionDenied
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response
from rest_framework.views import set_rollback

from marketlink_core.context import get_request_id
from marketlink_core.exceptions import DomainError, ErrorCode

logger = logging.getLogger("marketlink")

DEFAULT_ERROR_CODES: dict[int, str] = {
    400: ErrorCode.VALIDATION_ERROR,
    401: ErrorCode.NOT_AUTHENTICATED,
    403: ErrorCode.PERMISSION_DENIED,
    404: ErrorCode.NOT_FOUND,
    409: ErrorCode.RESOURCE_MODIFIED,
    422: ErrorCode.FAILED_PRECONDITION,
    428: ErrorCode.PRECONDITION_REQUIRED,
    429: ErrorCode.THROTTLED,
    500: ErrorCode.INTERNAL_SERVER_ERROR,
    503: ErrorCode.AI_UNAVAILABLE,
}

MYSQL_DUPLICATE_ENTRY = 1062
MYSQL_ROW_IS_REFERENCED = 1451
MYSQL_NO_REFERENCED_ROW = 1452
MYSQL_DATA_TOO_LONG = 1406
MYSQL_DEADLOCK = 1213
MYSQL_LOCK_WAIT_TIMEOUT = 1205


def api_response(
    *,
    message: str,
    data: Any = None,
    status_code: int = 200,
    request: Any = None,
    code: str | None = None,
    errors: dict[str, list[str]] | None = None,
    headers: dict[str, str] | None = None,
) -> Response:
    payload: dict[str, Any] = {
        "success": status_code < 400,
        "message": message,
        "request_id": getattr(request, "id", None) or get_request_id(),
        "data": data if data is not None else {},
        "errors": errors or {},
    }
    if status_code >= 400:
        # 4xx codes outside the catalog (405, 415...) are client mistakes, not server faults.
        fallback = ErrorCode.VALIDATION_ERROR if status_code < 500 else ErrorCode.INTERNAL_SERVER_ERROR
        payload["code"] = code or DEFAULT_ERROR_CODES.get(status_code, fallback)
    return Response(payload, status=status_code, headers=headers)


def flatten_errors(detail: Any, prefix: str = "") -> dict[str, list[str]]:
    flat: dict[str, list[str]] = {}
    if isinstance(detail, dict):
        for key, value in detail.items():
            name = "non_field_errors" if key in ("non_field_errors", "__all__") and not prefix else str(key)
            flat.update(flatten_errors(value, f"{prefix}.{name}" if prefix else name))
    elif isinstance(detail, list):
        if all(not isinstance(item, (dict, list)) for item in detail):
            flat[prefix or "non_field_errors"] = [str(item) for item in detail]
        else:
            for index, item in enumerate(detail):
                if item:
                    flat.update(flatten_errors(item, f"{prefix}.{index}" if prefix else str(index)))
    else:
        flat[prefix or "non_field_errors"] = [str(detail)]
    return flat


def _mysql_errno(exc: Exception) -> int | None:
    return exc.args[0] if exc.args and isinstance(exc.args[0], int) else None


def _log_access_denied(request: Any) -> None:
    # Lazy import: this module is loaded from settings, before the app registry is ready.
    from system.models import AuditAction
    from system.services import log_request_event

    try:
        log_request_event(request, action=AuditAction.ACCESS_DENIED, status_code=403)
    except Exception:  # noqa: BLE001 - an audit failure must never mask the 403 itself
        logger.exception("Failed to write ACCESS_DENIED audit log")


def custom_exception_handler(exc: Exception, context: dict[str, Any]) -> Response:
    request = context.get("request")

    def reply(message: str, status_code: int, code: str, errors: dict | None = None, data: dict | None = None) -> Response:
        headers = None
        if isinstance(exc, APIException):
            headers = {}
            if getattr(exc, "auth_header", None):
                headers["WWW-Authenticate"] = exc.auth_header
            if getattr(exc, "wait", None):
                headers["Retry-After"] = str(int(exc.wait))
        return api_response(
            message=message,
            data=data,
            status_code=status_code,
            code=code,
            errors=errors,
            request=request,
            headers=headers or None,
        )

    if isinstance(exc, DomainError):
        return reply(str(exc.detail), exc.status_code, exc.code, exc.errors, exc.data)

    if isinstance(exc, (ProtectedError, RestrictedError)):
        return reply("This record is still in use and cannot be removed.", 422, ErrorCode.RESOURCE_IN_USE)

    if isinstance(exc, IntegrityError):
        errno = _mysql_errno(exc)
        if errno in (MYSQL_ROW_IS_REFERENCED, MYSQL_NO_REFERENCED_ROW):
            return reply("This record is still in use or references missing data.", 422, ErrorCode.RESOURCE_IN_USE)
        if errno == MYSQL_DUPLICATE_ENTRY:
            return reply("This value already exists.", 400, ErrorCode.VALIDATION_ERROR)

    if isinstance(exc, DataError) and _mysql_errno(exc) == MYSQL_DATA_TOO_LONG:
        return reply("One of the values is too long.", 400, ErrorCode.VALIDATION_ERROR)

    if isinstance(exc, OperationalError) and _mysql_errno(exc) in (MYSQL_DEADLOCK, MYSQL_LOCK_WAIT_TIMEOUT):
        return reply("The system is busy. Please try again.", 409, ErrorCode.CONFLICT_RETRY)

    if isinstance(exc, DjangoValidationError):
        detail = exc.message_dict if hasattr(exc, "error_dict") else {"non_field_errors": exc.messages}
        return reply("Invalid input. Please check the highlighted fields.", 400, ErrorCode.VALIDATION_ERROR, flatten_errors(detail))

    if isinstance(exc, DRFValidationError):
        return reply("Invalid input. Please check the highlighted fields.", 400, ErrorCode.VALIDATION_ERROR, flatten_errors(exc.detail))

    if isinstance(exc, ParseError):
        return reply("The request body could not be parsed.", 400, ErrorCode.VALIDATION_ERROR)

    if isinstance(exc, (NotAuthenticated, AuthenticationFailed)):
        return reply("Please sign in to continue.", 401, ErrorCode.NOT_AUTHENTICATED)

    if isinstance(exc, (DRFPermissionDenied, DjangoPermissionDenied)):
        if request is not None:
            _log_access_denied(request)
        return reply("You do not have permission to access this resource.", 403, ErrorCode.PERMISSION_DENIED)

    if isinstance(exc, (NotFound, Http404, ObjectDoesNotExist)):
        return reply("The requested resource was not found.", 404, ErrorCode.NOT_FOUND)

    if isinstance(exc, Throttled):
        return reply("Too many requests. Please try again in a few minutes.", 429, ErrorCode.THROTTLED)

    if isinstance(exc, APIException):
        return reply(str(exc.detail), exc.status_code, DEFAULT_ERROR_CODES.get(exc.status_code, ErrorCode.VALIDATION_ERROR))

    logger.exception("Unhandled server exception", exc_info=exc)
    set_rollback()
    return reply("Something went wrong. Please try again later.", 500, ErrorCode.INTERNAL_SERVER_ERROR)
