"""Tests for the in-memory rate limiter and the login attempt dependency."""

from types import SimpleNamespace

import pytest

from src.api.dependencies import limit_login_attempts
from src.api.rate_limit import RateLimiter
from src.libs.exceptions.exceptions import TooManyRequestsException


class FakeClock:
    """A monotonic clock that the test moves forward by hand."""

    def __init__(self, now: float = 1000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def limiter(clock: FakeClock, limit: int = 3, max_keys: int = 100) -> RateLimiter:
    return RateLimiter(limit, window_seconds=60, max_keys=max_keys, clock=clock)


class TestRateLimiter:
    """RateLimiter allows `limit` hits per key in each fixed window."""

    def test_hits_up_to_the_limit_are_allowed(self, clock: FakeClock):
        """
        GIVEN a limit of 3 per window
        WHEN one key is hit 3 times
        THEN no hit is refused
        """
        rate_limiter = limiter(clock)

        for _ in range(3):
            rate_limiter.hit("10.0.0.1")

    def test_hit_over_the_limit_is_refused_with_retry_after(self, clock: FakeClock):
        """
        GIVEN a key that used its 3 hits, 20 s into a 60 s window
        WHEN it is hit again
        THEN TooManyRequestsException is raised
        AND retry_after is the 40 s until the window ends
        """
        rate_limiter = limiter(clock)
        clock.now = 1020.0  # the window [960, 1020) ended; [1020, 1080) starts
        for _ in range(3):
            rate_limiter.hit("10.0.0.1")
        clock.now = 1040.0

        with pytest.raises(TooManyRequestsException) as raised:
            rate_limiter.hit("10.0.0.1")

        assert raised.value.retry_after == 40

    def test_retry_after_is_at_least_one_second(self, clock: FakeClock):
        """
        GIVEN a key over its limit 0.2 s before the window ends
        WHEN it is hit again
        THEN retry_after is rounded up to 1 s, never 0
        """
        rate_limiter = limiter(clock, limit=1)
        clock.now = 1079.8
        rate_limiter.hit("10.0.0.1")

        with pytest.raises(TooManyRequestsException) as raised:
            rate_limiter.hit("10.0.0.1")

        assert raised.value.retry_after == 1

    def test_keys_are_counted_separately(self, clock: FakeClock):
        """
        GIVEN one key that used its limit
        WHEN another key is hit
        THEN the other key is allowed
        """
        rate_limiter = limiter(clock, limit=1)
        rate_limiter.hit("10.0.0.1")

        rate_limiter.hit("10.0.0.2")

    def test_a_new_window_resets_every_count(self, clock: FakeClock):
        """
        GIVEN a key that used its limit
        WHEN the next window starts
        THEN the key is allowed again
        """
        rate_limiter = limiter(clock, limit=1)
        rate_limiter.hit("10.0.0.1")
        clock.now += 60

        rate_limiter.hit("10.0.0.1")

    def test_new_keys_are_refused_when_the_table_is_full(self, clock: FakeClock):
        """
        GIVEN a table that holds 2 keys and has 2 keys in this window
        WHEN a third key is hit
        THEN it is refused, so many addresses cannot fill the memory
        AND the keys in the table are still counted normally
        """
        rate_limiter = limiter(clock, max_keys=2)
        rate_limiter.hit("10.0.0.1")
        rate_limiter.hit("10.0.0.2")

        with pytest.raises(TooManyRequestsException):
            rate_limiter.hit("10.0.0.3")
        rate_limiter.hit("10.0.0.1")

    @pytest.mark.parametrize(
        "kwargs",
        [{"limit": 0}, {"window_seconds": 0}, {"max_keys": 0}],
        ids=["limit", "window", "max-keys"],
    )
    def test_non_positive_settings_are_rejected(self, kwargs):
        """
        GIVEN a limit, window or table size of 0
        WHEN the limiter is created
        THEN ValueError is raised
        """
        arguments = {"limit": 1, "window_seconds": 60, "max_keys": 1} | kwargs

        with pytest.raises(ValueError):
            RateLimiter(**arguments)


class TestLimitLoginAttempts:
    """limit_login_attempts() counts one attempt per client address."""

    def test_request_without_client_address_shares_one_key(self, clock: FakeClock):
        """
        GIVEN requests whose client address is unknown (for example a Unix socket)
        WHEN they exceed the limit
        THEN they are refused together under one key
        """
        rate_limiter = limiter(clock, limit=1)
        request = SimpleNamespace(client=None)
        limit_login_attempts(request, rate_limiter)  # type: ignore[arg-type]

        with pytest.raises(TooManyRequestsException):
            limit_login_attempts(request, rate_limiter)  # type: ignore[arg-type]
