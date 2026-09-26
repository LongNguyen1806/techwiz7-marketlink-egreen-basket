import hashlib

from rest_framework.throttling import SimpleRateThrottle


class CheckOnlyRateThrottle(SimpleRateThrottle):
    """A rate limit whose counter only grows when the view calls record().

    SimpleRateThrottle counts every request. Here allow_request() only checks the limit,
    so the view decides which outcomes count (for example only failed sign-ins).
    """

    def allow_request(self, request, view) -> bool:
        if self.rate is None:
            return True
        self.key = self.get_cache_key(request, view)
        if self.key is None:
            return True
        self.now = self.timer()
        self.history = self._live_history()
        if len(self.history) >= self.num_requests:
            return self.throttle_failure()
        return True

    def record(self) -> None:
        if getattr(self, "key", None) is None:
            return
        self.now = self.timer()
        history = self._live_history()
        history.insert(0, self.now)
        self.cache.set(self.key, history, self.duration)

    def _live_history(self) -> list[float]:
        history = self.cache.get(self.key, [])
        while history and history[-1] <= self.now - self.duration:
            history.pop()
        return history


class LoginEmailThrottle(CheckOnlyRateThrottle):
    """AU-03 / AU-09: failed sign-ins per email, whatever IP they come from.

    Only wrong-password attempts are recorded (by the view), so a user who signs in
    successfully many times is never locked out.
    """

    scope = "login_email"

    def get_cache_key(self, request, view) -> str | None:
        data = request.data if hasattr(request.data, "get") else {}
        email = data.get("email")
        if not isinstance(email, str) or not email.strip():
            return None
        # Hashed: the cache key never holds the raw email address.
        ident = hashlib.sha256(email.strip().lower().encode("utf-8")).hexdigest()
        return self.cache_format % {"scope": self.scope, "ident": ident}


class RecordableThrottleViewMixin:
    """Keeps the throttle instances of this request so the view can record() one later."""

    def get_throttles(self):
        self.throttle_instances = super().get_throttles()
        return self.throttle_instances

    def record_throttle(self, throttle_class: type[CheckOnlyRateThrottle]) -> None:
        for throttle in getattr(self, "throttle_instances", []):
            if isinstance(throttle, throttle_class):
                throttle.record()
