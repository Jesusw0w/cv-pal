import pytest

from cv_pal.exceptions import RateLimitedError
from cv_pal.rate_limit import InMemoryRateLimiter


def test_allows_requests_up_to_the_limit() -> None:
    """The configured number of requests is permitted."""
    limiter = InMemoryRateLimiter(requests=3, window_seconds=60)

    for _ in range(3):
        limiter.check("client")


def test_rejects_the_request_after_the_limit() -> None:
    """The next request past the limit is rejected."""
    limiter = InMemoryRateLimiter(requests=3, window_seconds=60)
    for _ in range(3):
        limiter.check("client")

    with pytest.raises(RateLimitedError) as excinfo:
        limiter.check("client")

    assert excinfo.value.retry_after > 0


def test_limits_are_per_key() -> None:
    """One client exhausting its quota does not affect another."""
    limiter = InMemoryRateLimiter(requests=1, window_seconds=60)
    limiter.check("client-a")

    limiter.check("client-b")

    with pytest.raises(RateLimitedError):
        limiter.check("client-a")


def test_window_expiry_restores_quota() -> None:
    """Quota returns once the window has passed."""
    limiter = InMemoryRateLimiter(requests=1, window_seconds=0.05)
    limiter.check("client")

    # The window is measured monotonically; advancing past it frees the slot.
    import time

    time.sleep(0.06)

    limiter.check("client")


def test_failures_below_the_threshold_do_not_lock() -> None:
    """A few wrong attempts are tolerated without backoff."""
    limiter = InMemoryRateLimiter(lockout_threshold=3)

    for _ in range(3):
        limiter.record_failure("account")

    limiter.check_locked("account")


def test_failures_past_the_threshold_lock_the_key() -> None:
    """Exceeding the failure threshold starts the backoff."""
    limiter = InMemoryRateLimiter(lockout_threshold=3, lockout_base_seconds=30)
    for _ in range(4):
        limiter.record_failure("account")

    with pytest.raises(RateLimitedError) as excinfo:
        limiter.check_locked("account")

    assert excinfo.value.retry_after > 0


def test_backoff_grows_with_further_failures() -> None:
    """Each failure past the threshold doubles the wait."""
    limiter = InMemoryRateLimiter(lockout_threshold=1, lockout_base_seconds=10)
    for _ in range(2):
        limiter.record_failure("account")
    with pytest.raises(RateLimitedError) as first:
        limiter.check_locked("account")

    limiter.record_failure("account")
    with pytest.raises(RateLimitedError) as second:
        limiter.check_locked("account")

    assert second.value.retry_after > first.value.retry_after


def test_backoff_is_capped() -> None:
    """The wait does not grow without bound."""
    limiter = InMemoryRateLimiter(
        lockout_threshold=1, lockout_base_seconds=10, lockout_cap_seconds=60
    )

    for _ in range(20):
        limiter.record_failure("account")

    with pytest.raises(RateLimitedError) as excinfo:
        limiter.check_locked("account")

    assert excinfo.value.retry_after <= 61


def test_reset_clears_the_failure_history() -> None:
    """A successful attempt clears the backoff."""
    limiter = InMemoryRateLimiter(lockout_threshold=1, lockout_base_seconds=30)
    for _ in range(3):
        limiter.record_failure("account")

    limiter.reset("account")

    limiter.check_locked("account")
