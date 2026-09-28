from typing import Any

from rest_framework.exceptions import APIException


class ErrorCode:
    VALIDATION_ERROR = "VALIDATION_ERROR"
    EMAIL_EXISTS = "EMAIL_EXISTS"
    INSUFFICIENT_STOCK = "INSUFFICIENT_STOCK"
    INVALID_STATUS_TRANSITION = "INVALID_STATUS_TRANSITION"

    NOT_AUTHENTICATED = "NOT_AUTHENTICATED"
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    TOKEN_INVALID = "TOKEN_INVALID"

    ACCOUNT_LOCKED = "ACCOUNT_LOCKED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    ACTION_NOT_PERMITTED_FOR_ROLE = "ACTION_NOT_PERMITTED_FOR_ROLE"
    FARMER_NOT_APPROVED = "FARMER_NOT_APPROVED"
    FARMER_SUSPENDED = "FARMER_SUSPENDED"

    NOT_FOUND = "NOT_FOUND"

    RESOURCE_MODIFIED = "RESOURCE_MODIFIED"
    IDEMPOTENCY_IN_PROGRESS = "IDEMPOTENCY_IN_PROGRESS"
    CONFLICT_RETRY = "CONFLICT_RETRY"

    OPEN_ORDER_LIMIT_EXCEEDED = "OPEN_ORDER_LIMIT_EXCEEDED"
    CUTOFF_PASSED = "CUTOFF_PASSED"
    CUTOFF_NOT_REACHED = "CUTOFF_NOT_REACHED"
    PICKUP_ALREADY_STARTED = "PICKUP_ALREADY_STARTED"
    PICKUP_NOT_ENDED = "PICKUP_NOT_ENDED"
    SLOT_NOT_AVAILABLE = "SLOT_NOT_AVAILABLE"
    PRODUCT_NOT_AVAILABLE = "PRODUCT_NOT_AVAILABLE"
    REVIEW_NOT_ALLOWED = "REVIEW_NOT_ALLOWED"
    REPLY_ALREADY_EXISTS = "REPLY_ALREADY_EXISTS"
    RESOURCE_IN_USE = "RESOURCE_IN_USE"
    IDEMPOTENCY_KEY_REUSED = "IDEMPOTENCY_KEY_REUSED"
    FAILED_PRECONDITION = "FAILED_PRECONDITION"

    PRECONDITION_REQUIRED = "PRECONDITION_REQUIRED"

    THROTTLED = "THROTTLED"

    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    AI_UNAVAILABLE = "AI_UNAVAILABLE"


class DomainError(APIException):
    status_code = 400
    default_code = ErrorCode.VALIDATION_ERROR
    default_detail = "Invalid request."

    def __init__(
        self,
        message: str | None = None,
        *,
        code: str | None = None,
        errors: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(detail=message or self.default_detail)
        self.code = code or self.default_code
        self.errors = errors or {}
        self.data = data or {}


class BusinessValidationError(DomainError):
    status_code = 400
    default_code = ErrorCode.VALIDATION_ERROR
    default_detail = "Invalid request."


class AuthenticationError(DomainError):
    status_code = 401
    default_code = ErrorCode.NOT_AUTHENTICATED
    default_detail = "Please sign in to continue."


class ForbiddenActionError(DomainError):
    status_code = 403
    default_code = ErrorCode.ACTION_NOT_PERMITTED_FOR_ROLE
    default_detail = "You are not allowed to perform this action."


class ResourceNotFoundError(DomainError):
    status_code = 404
    default_code = ErrorCode.NOT_FOUND
    default_detail = "The requested resource was not found."


class ConflictError(DomainError):
    status_code = 409
    default_code = ErrorCode.RESOURCE_MODIFIED
    default_detail = "This record was changed by someone else. Please reload."


class UnprocessableEntityError(DomainError):
    status_code = 422
    default_code = ErrorCode.FAILED_PRECONDITION
    default_detail = "This action cannot be completed right now."


class PreconditionRequiredError(DomainError):
    status_code = 428
    default_code = ErrorCode.PRECONDITION_REQUIRED
    default_detail = "A required request header is missing."


class ServiceUnavailableError(DomainError):
    status_code = 503
    default_code = ErrorCode.AI_UNAVAILABLE
    default_detail = "The assistant is temporarily unavailable."
