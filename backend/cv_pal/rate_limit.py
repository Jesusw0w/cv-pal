"""Rate limiting and failed-login backoff.

The implementation is in-process, which is correct for a single-worker deployment and
for development. It is deliberately behind a Protocol: when Redis arrives for the job
queue, a shared implementation can be dropped in without touching the routers.

**Known limitation:** with multiple uvicorn workers each process keeps its own
counters, so the effective limit is multiplied by the worker count. Fine for a personal
deployment, not sufficient as the only defence for a public one.
"""

import time
from collections import defaultdict, deque
from typing import Protocol

from cv_pal.constants import (
    DEFAULT_LOCKOUT_BACKOFF_CAP_SECONDS,
    DEFAULT_LOCKOUT_BASE_SECONDS,
    DEFAULT_LOCKOUT_THRESHOLD,
    DEFAULT_RATE_LIMIT_MAX_TRACKED_KEYS,
    DEFAULT_RATE_LIMIT_REQUESTS,
    DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
)
from cv_pal.exceptions import RateLimitedError


class RateLimiter(Protocol):
    """Request throttling and repeated-failure backoff."""

    def check(self, key: str) -> None:
        """Consume one unit of quota for ``key``.

        Args:
            key: The bucket to charge, e.g. a client address.

        Raises:
            RateLimitedError: If the quota for this window is exhausted.
        """
        ...

    def check_locked(self, key: str) -> None:
        """Reject the request if ``key`` is in failure backoff.

        Args:
            key: The bucket to test, e.g. a submitted email address.

        Raises:
            RateLimitedError: If the key is currently locked out.
        """
        ...

    def record_failure(self, key: str) -> None:
        """Record a failed attempt for ``key``.

        Args:
            key: The bucket to charge.
        """
        ...

    def reset(self, key: str) -> None:
        """Clear the failure history for ``key`` after a success.

        Args:
            key: The bucket to clear.
        """
        ...


class InMemoryRateLimiter:
    """Sliding-window rate limiting with exponential failure backoff."""

    def __init__(
        self,
        *,
        requests: int = DEFAULT_RATE_LIMIT_REQUESTS,
        window_seconds: float = DEFAULT_RATE_LIMIT_WINDOW_SECONDS,
        lockout_threshold: int = DEFAULT_LOCKOUT_THRESHOLD,
        lockout_base_seconds: float = DEFAULT_LOCKOUT_BASE_SECONDS,
        lockout_cap_seconds: float = DEFAULT_LOCKOUT_BACKOFF_CAP_SECONDS,
    ) -> None:
        """Initialise the limiter.

        Args:
            requests: Requests permitted per window, per key.
            window_seconds: Length of the sliding window.
            lockout_threshold: Consecutive failures tolerated before backoff starts.
            lockout_base_seconds: Backoff after the first excess failure; it doubles
                with each further failure.
            lockout_cap_seconds: Upper bound on the backoff.
        """
        self._requests = requests
        self._window = window_seconds
        self._lockout_threshold = lockout_threshold
        self._lockout_base = lockout_base_seconds
        self._lockout_cap = lockout_cap_seconds
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)
        self._failures: dict[str, tuple[int, float]] = {}

    def _now(self) -> float:
        """Return a monotonic timestamp.

        Returns:
            Seconds from an arbitrary origin, unaffected by clock changes.
        """
        return time.monotonic()

    def _prune(self, now: float) -> None:
        """Drop expired state so the maps cannot grow without bound.

        Args:
            now: The current monotonic time.
        """
        if len(self._hits) > DEFAULT_RATE_LIMIT_MAX_TRACKED_KEYS:
            stale = [
                key
                for key, hits in self._hits.items()
                if not hits or now - hits[-1] > self._window
            ]
            for key in stale:
                del self._hits[key]

        if len(self._failures) > DEFAULT_RATE_LIMIT_MAX_TRACKED_KEYS:
            expired = [
                key
                for key, (_, until) in self._failures.items()
                if now >= until + self._lockout_cap
            ]
            for key in expired:
                del self._failures[key]

    def check(self, key: str) -> None:
        """Consume one unit of quota for ``key``.

        Args:
            key: The bucket to charge.

        Raises:
            RateLimitedError: If the quota for this window is exhausted.
        """
        now = self._now()
        self._prune(now)

        hits = self._hits[key]
        cutoff = now - self._window
        while hits and hits[0] <= cutoff:
            hits.popleft()

        if len(hits) >= self._requests:
            retry_after = max(1, int(hits[0] + self._window - now) + 1)
            raise RateLimitedError(retry_after)

        hits.append(now)

    def check_locked(self, key: str) -> None:
        """Reject the request if ``key`` is in failure backoff.

        Args:
            key: The bucket to test.

        Raises:
            RateLimitedError: If the key is currently locked out.
        """
        entry = self._failures.get(key)
        if entry is None:
            return

        _, locked_until = entry
        now = self._now()
        if now < locked_until:
            raise RateLimitedError(max(1, int(locked_until - now) + 1))

    def record_failure(self, key: str) -> None:
        """Record a failed attempt and extend the backoff if past the threshold.

        Args:
            key: The bucket to charge.
        """
        now = self._now()
        self._prune(now)

        count, _ = self._failures.get(key, (0, 0.0))
        count += 1

        if count <= self._lockout_threshold:
            self._failures[key] = (count, 0.0)
            return

        # First excess failure waits lockout_base, and each further one doubles it.
        exponent = count - self._lockout_threshold - 1
        delay = min(self._lockout_base * (2**exponent), self._lockout_cap)
        self._failures[key] = (count, now + delay)

    def reset(self, key: str) -> None:
        """Clear the failure history for ``key``.

        Args:
            key: The bucket to clear.
        """
        self._failures.pop(key, None)


_limiter = InMemoryRateLimiter()


def get_rate_limiter() -> RateLimiter:
    """Provide the process-wide rate limiter.

    Used as a FastAPI dependency so tests can substitute a fresh instance.

    Returns:
        The shared limiter.
    """
    return _limiter
