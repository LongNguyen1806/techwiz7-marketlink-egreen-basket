"""How many assistant answers someone may get per day (AI_CHAT_DAILY_LIMIT_*).

Visitors are counted per IP (behind a proxy, NUM_PROXIES decides which address that is),
signed-in users per account. The count lives in the shared cache (Redis) and expires at local
midnight. Only answers the model actually gave are counted: an outage never uses up someone's day.

The cap is never revealed: a capped request gets the same neutral "busy" reply as an outage.
"""

from datetime import datetime, time, timedelta

from django.conf import settings
from django.core.cache import cache
from django.utils import timezone
from rest_framework.throttling import SimpleRateThrottle

from chat_bot.ai_chatbot import Asker


class _Ident(SimpleRateThrottle):
    """Borrowed for DRF's client-IP logic (X-Forwarded-For under NUM_PROXIES)."""

    rate = "1/day"

    def get_cache_key(self, request, view):  # pragma: no cover - not used as a throttle
        return None


def _identity(request, asker: Asker) -> str:
    if asker.user is not None:
        return f"user:{asker.user.pk}"
    return f"ip:{_Ident().get_ident(request)}"


def _limit(asker: Asker) -> int:
    return settings.AI_CHAT_DAILY_LIMIT_USER if asker.user is not None else settings.AI_CHAT_DAILY_LIMIT_GUEST


def _key(request, asker: Asker) -> str:
    return f"chat:daily:{timezone.localdate().isoformat()}:{_identity(request, asker)}"


def _seconds_to_midnight() -> int:
    now = timezone.localtime()
    midnight = timezone.make_aware(datetime.combine(now.date() + timedelta(days=1), time.min))
    return max(60, int((midnight - now).total_seconds()))


def used_up(request, asker: Asker) -> bool:
    limit = _limit(asker)
    return limit > 0 and (cache.get(_key(request, asker)) or 0) >= limit


def record_answer(request, asker: Asker) -> None:
    if _limit(asker) <= 0:
        return
    key = _key(request, asker)
    cache.add(key, 0, timeout=_seconds_to_midnight())
    try:
        cache.incr(key)
    except ValueError:  # expired between add and incr (just past midnight)
        cache.set(key, 1, timeout=_seconds_to_midnight())
