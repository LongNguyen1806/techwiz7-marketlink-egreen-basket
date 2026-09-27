from marketlink_core.exceptions import ErrorCode, UnprocessableEntityError


class ReviewNotAllowedError(UnprocessableEntityError):
    default_code = ErrorCode.REVIEW_NOT_ALLOWED
    default_detail = "This order cannot be reviewed. Only completed orders can be reviewed, once."
