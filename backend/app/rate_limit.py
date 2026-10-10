"""Small, concurrency-safe fixed-window rate limiter for anonymous prototype APIs."""

from __future__ import annotations

from collections import deque
from threading import Lock
from time import monotonic


class FixedWindowRateLimiter:
    """Allow a bounded number of requests per client key over a rolling window."""

    def __init__(self, max_requests: int, window_seconds: float) -> None:
        if max_requests <= 0 or window_seconds <= 0:
            raise ValueError("rate-limit values must be positive")
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._buckets: dict[str, deque[float]] = {}
        self._lock = Lock()

    def check(self, key: str) -> tuple[bool, int]:
        """Return whether the request is allowed and a conservative retry delay."""

        current = monotonic()
        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            cutoff = current - self._window_seconds
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self._max_requests:
                retry_after = max(1, int(self._window_seconds - (current - bucket[0])) + 1)
                return False, retry_after
            bucket.append(current)
            return True, 0
