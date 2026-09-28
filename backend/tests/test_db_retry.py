from types import SimpleNamespace
from unittest import mock

from django.db import OperationalError
from django.test import SimpleTestCase

from marketlink_core.exceptions import ConflictError, ErrorCode
from marketlink_core.services.db_retry import run_with_deadlock_retry
from orders.services import fsm


def _failing(errno: int, times: int):
    calls = {"count": 0}

    def fn():
        calls["count"] += 1
        if calls["count"] <= times:
            raise OperationalError(errno, "simulated")
        return "done"

    return fn, calls


class DeadlockRetryTestCase(SimpleTestCase):
    def test_deadlock_is_retried_once(self):
        fn, calls = _failing(1213, times=1)
        self.assertEqual(run_with_deadlock_retry(fn), "done")
        self.assertEqual(calls["count"], 2)

    def test_second_deadlock_becomes_conflict_retry(self):
        fn, calls = _failing(1213, times=2)
        with self.assertRaises(ConflictError) as ctx:
            run_with_deadlock_retry(fn)
        self.assertEqual(ctx.exception.code, ErrorCode.CONFLICT_RETRY)
        self.assertEqual(calls["count"], 2)

    def test_lock_wait_timeout_is_not_retried(self):
        fn, calls = _failing(1205, times=1)
        with self.assertRaises(OperationalError):
            run_with_deadlock_retry(fn)
        self.assertEqual(calls["count"], 1)

    def test_no_retry_inside_outer_transaction(self):
        fn, calls = _failing(1213, times=1)
        in_atomic = SimpleNamespace(in_atomic_block=True)
        with mock.patch.object(fsm.transaction, "get_connection", return_value=in_atomic):
            with self.assertRaises(OperationalError):
                fsm.run_with_retry_if_top_level(fn)
        self.assertEqual(calls["count"], 1)

    def test_retry_at_top_level(self):
        fn, calls = _failing(1213, times=1)
        top_level = SimpleNamespace(in_atomic_block=False)
        with mock.patch.object(fsm.transaction, "get_connection", return_value=top_level):
            self.assertEqual(fsm.run_with_retry_if_top_level(fn), "done")
        self.assertEqual(calls["count"], 2)
