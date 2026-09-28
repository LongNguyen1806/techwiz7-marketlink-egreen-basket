from unittest import mock

import pytest
from django.core.cache import cache

from orders.exceptions import IdempotencyInProgressError, IdempotencyKeyReusedError
from orders.services import idempotency_service
from orders.services.idempotency_service import fingerprint, run_idempotent

KEY = "5f0c2c1e-8a3b-4b8e-9d7e-2a61c0f4b9a1"
CACHE_KEY = f"idem:1:{KEY}"


def _run(payload, action=lambda: (201, {"ok": True}), user_id=1):
    return run_idempotent(user_id=user_id, key=KEY, payload=payload, action=action)


class TestRunIdempotent:
    def test_first_call_runs_action(self):
        result = _run({"a": 1})

        assert (result.status, result.body, result.replayed) == (201, {"ok": True}, False)

    def test_same_payload_replays_stored_response(self):
        _run({"a": 1, "b": 2})
        calls = []

        result = _run({"b": 2, "a": 1}, action=lambda: calls.append(1) or (201, {}))

        assert (result.body, result.replayed, calls) == ({"ok": True}, True, [])

    def test_different_payload_with_same_key_is_rejected(self):
        _run({"a": 1})

        with pytest.raises(IdempotencyKeyReusedError):
            _run({"a": 2})

    def test_request_still_processing_is_rejected(self):
        idempotency_service._claim(user_id=1, key=KEY, request_hash=fingerprint({"a": 1}))

        with pytest.raises(IdempotencyInProgressError):
            _run({"a": 1})

    def test_failed_action_releases_the_key(self):
        def boom():
            raise RuntimeError("stock changed")

        with pytest.raises(RuntimeError):
            _run({"a": 1}, action=boom)

        assert _run({"a": 2}).replayed is False

    def test_keys_are_scoped_per_user(self):
        _run({"a": 1}, user_id=1)

        assert _run({"a": 2}, user_id=2).replayed is False

    def test_failed_request_never_erases_another_requests_result(self):
        def slow_then_fail():
            cache.set(CACHE_KEY, {"state": "done", "hash": fingerprint({"a": 1}), "status": 201, "body": {"id": 7}})
            raise RuntimeError("limit exceeded")

        with pytest.raises(RuntimeError):
            _run({"a": 1}, action=slow_then_fail)

        replay = _run({"a": 1})
        assert (replay.replayed, replay.body) == (True, {"id": 7})

    def test_key_freed_between_add_and_get_is_claimed(self):
        with mock.patch.object(idempotency_service.cache, "add", side_effect=[False, True]), \
                mock.patch.object(idempotency_service.cache, "get", return_value=None):
            result = _run({"a": 1})

        assert result.replayed is False

    def test_result_cache_failure_still_returns_the_response(self):
        with mock.patch.object(idempotency_service.cache, "set", side_effect=ConnectionError("redis down")):
            result = _run({"a": 1})

        assert (result.status, result.replayed) == (201, False)


class TestReleaseFailures:
    def test_cache_error_while_releasing_keeps_the_original_error(self):
        def boom():
            raise RuntimeError("stock changed")

        with mock.patch.object(idempotency_service.cache, "get", side_effect=ConnectionError("redis down")):
            with pytest.raises(RuntimeError):
                _run({"a": 1}, action=boom)
