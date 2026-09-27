from marketlink_core.exceptions import BusinessValidationError, ConflictError, ErrorCode, UnprocessableEntityError


class SlotNotAvailableError(UnprocessableEntityError):
    default_code = ErrorCode.SLOT_NOT_AVAILABLE
    default_detail = "The selected pickup slot is not available"


class CutoffPassedError(UnprocessableEntityError):
    default_code = ErrorCode.CUTOFF_PASSED
    default_detail = "The order deadline for this pickup slot has passed"


class ProductNotAvailableError(UnprocessableEntityError):
    default_code = ErrorCode.PRODUCT_NOT_AVAILABLE
    default_detail = "Some products are no longer available"


class InsufficientStockError(BusinessValidationError):
    default_code = ErrorCode.INSUFFICIENT_STOCK
    default_detail = "Some products do not have enough stock"


class OpenOrderLimitExceededError(UnprocessableEntityError):
    default_code = ErrorCode.OPEN_ORDER_LIMIT_EXCEEDED
    default_detail = "You have reached the limit of open orders"


class IdempotencyInProgressError(ConflictError):
    default_code = ErrorCode.IDEMPOTENCY_IN_PROGRESS
    default_detail = "This order is already being processed"


class IdempotencyKeyReusedError(UnprocessableEntityError):
    default_code = ErrorCode.IDEMPOTENCY_KEY_REUSED
    default_detail = "This Idempotency-Key was already used for a different request"
