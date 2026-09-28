from typing import Any, Callable, TypeVar

from django.db import OperationalError

from marketlink_core.exceptions import ConflictError, ErrorCode

MYSQL_DEADLOCK = 1213

T = TypeVar("T")


def run_with_deadlock_retry(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:
    for attempt in range(2):
        try:
            return fn(*args, **kwargs)
        except OperationalError as exc:
            if not exc.args or exc.args[0] != MYSQL_DEADLOCK:
                raise
            if attempt == 1:
                raise ConflictError(
                    "The system is busy. Please try again.", code=ErrorCode.CONFLICT_RETRY
                ) from exc
    raise AssertionError("unreachable")
