"""Shared Gemini plumbing: the model chain, error sorting, retries and the free-tier quota.

Used by the AI listing review (catalog/ai_review) and the assistant (chat_bot). Both call the
model through ``call_with_fallback`` so a quota or outage is handled the same way everywhere.
"""

import logging
import time
from collections.abc import Callable
from typing import TypeVar

from django.conf import settings

logger = logging.getLogger("marketlink")

T = TypeVar("T")

RETRY_DELAYS_S = (2.0, 6.0)
# Per-minute rate limits: wait as long as Gemini asks, but never stall a request longer.
MAX_RATE_LIMIT_WAIT_S = 30.0


class AIUnavailable(Exception):
    """The model could not be asked or its answer could not be used."""


def model_chain(primary: str, fallbacks: list[str]) -> list[str]:
    """The primary model, then the fallbacks; each has its own free-tier quota."""
    return list(dict.fromkeys(name.strip() for name in [primary, *fallbacks] if name and name.strip()))


def _retry_seconds(value) -> float | None:
    """RetryInfo.retryDelay ("1.7s" or "12s") as seconds."""
    try:
        return float(str(value).rstrip("s"))
    except (TypeError, ValueError):
        return None


def classify_error(code: int | None, details) -> tuple[str, float | None, str]:
    """What to do about a failed call: ("retry", wait_s, why) | ("next_model", None, why) | ("fail", None, why).

    * 429 per-day quota: this model is done for today -> try the next model.
    * 429 per-minute: wait as long as Gemini asks (capped), then retry the same model.
    * 404: the key cannot use this model -> next model.
    * 5xx / timeouts: retry with backoff.
    * other 4xx (bad key, bad request): retrying cannot help.
    """
    error = details.get("error", details) if isinstance(details, dict) else {}
    extra = error.get("details", []) if isinstance(error, dict) else []
    quota_ids = [
        violation.get("quotaId", "")
        for item in extra
        if "QuotaFailure" in str(item.get("@type", ""))
        for violation in item.get("violations", [])
    ]
    wait = next((_retry_seconds(item.get("retryDelay")) for item in extra if "RetryInfo" in str(item.get("@type", ""))), None)
    if code == 429:
        if any("PerDay" in quota_id for quota_id in quota_ids):
            return "next_model", None, "daily free-tier quota used up"
        return "retry", min(wait if wait is not None else 10.0, MAX_RATE_LIMIT_WAIT_S), "rate limited"
    if code == 404:
        return "next_model", None, "model not available to this key"
    if code is None or code >= 500:
        return "retry", None, f"server error {code}" if code else "no response"
    return "fail", None, f"request refused ({code})"


def make_client(timeout_ms: int):
    """A client for the configured key. Raises AIUnavailable when there is no key or no SDK."""
    if not settings.GEMINI_API_KEY:
        raise AIUnavailable("No GEMINI_API_KEY is configured.")
    try:
        from google import genai
        from google.genai import types
    except ImportError as exc:  # pragma: no cover - dependency is in requirements.txt
        raise AIUnavailable("The google-genai package is not installed.") from exc
    return genai.Client(api_key=settings.GEMINI_API_KEY, http_options=types.HttpOptions(timeout=timeout_ms))


def call_with_fallback(models: list[str], attempt: Callable[[str], T], *, deadline: float | None = None) -> tuple[T, str]:
    """Run ``attempt(model)`` on the first model that answers; returns (result, model).

    ``deadline`` (time.monotonic) stops waiting and retrying once a request has used its time.
    AIUnavailable raised by ``attempt`` (an unusable answer) propagates as is.
    """
    from google.genai import errors

    problems = []
    for model in models:
        for tries in range(len(RETRY_DELAYS_S) + 1):
            try:
                return attempt(model), model
            except AIUnavailable:
                raise
            except errors.APIError as exc:
                action, wait, why = classify_error(exc.code, getattr(exc, "details", None))
            except Exception as exc:  # timeouts, network
                action, wait, why = "retry", None, type(exc).__name__

            logger.warning("Gemini: %s on %s (attempt %s, %s)", why, model, tries + 1, action)
            if action == "fail":
                raise AIUnavailable(f"Gemini {why} on {model}.")
            pause = wait if wait is not None else RETRY_DELAYS_S[min(tries, len(RETRY_DELAYS_S) - 1)]
            out_of_time = deadline is not None and time.monotonic() + pause >= deadline
            if action == "next_model" or tries == len(RETRY_DELAYS_S) or out_of_time:
                problems.append(f"{model}: {why}")
                if out_of_time and action != "next_model":
                    raise AIUnavailable(f"No model answered in time ({'; '.join(problems)}).")
                break
            time.sleep(pause)
    raise AIUnavailable(f"No model answered ({'; '.join(problems)}).")


def is_quota_problem(error: AIUnavailable) -> bool:
    """True when every model failed for quota reasons (worth telling a human, not retrying)."""
    text = str(error)
    return "quota" in text and "server error" not in text

