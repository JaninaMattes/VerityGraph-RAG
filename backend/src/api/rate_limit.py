"""A small in-memory rate limiter for endpoints that are expensive to abuse."""

import math
import time
from collections.abc import Callable

from src.libs.exceptions.exceptions import TooManyRequestsException


class RateLimiter:
    """Allow at most `limit` hits per key in each fixed window of `window_seconds`.

    The counts live in this process only: with N API processes a client gets N times
    the limit. The table holds at most `max_keys` keys per window, so many client
    addresses cannot fill the memory; when it is full, new keys are refused.
    """

    def __init__(
        self,
        limit: int,
        *,
        window_seconds: float = 60,
        max_keys: int = 100_000,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if limit < 1 or window_seconds <= 0 or max_keys < 1:
            raise ValueError("limit, window_seconds and max_keys must be positive.")
        self.limit = limit
        self._window_seconds = window_seconds
        self._max_keys = max_keys
        self._clock = clock
        self._window = -1
        self._counts: dict[str, int] = {}

    def hit(self, key: str) -> None:
        """Count one hit of `key`.

        Raise TooManyRequestsException, with the seconds until the window ends, if
        the key has used its limit or the table is full.
        """
        now = self._clock()
        window = int(now // self._window_seconds)
        if window != self._window:
            self._window, self._counts = window, {}

        count = self._counts.get(key, 0)
        if count >= self.limit or (count == 0 and len(self._counts) >= self._max_keys):
            window_end = (window + 1) * self._window_seconds
            raise TooManyRequestsException(retry_after=math.ceil(window_end - now))
        self._counts[key] = count + 1
