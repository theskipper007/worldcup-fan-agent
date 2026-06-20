"""Shared rate limiter — the single API-Football budget all agents pass through.

See ../docs/api-football.md (rate-limit ruleset). The free tier is 10 requests/minute and the
budget is SHARED across all four agents; no agent may independently decide it is safe to fire.

This token-bucket implementation is functional (the rest of the backend is still stubbed). It is
intentionally small and dependency-free so it can be unit-tested in isolation.
"""

from __future__ import annotations

import threading
import time


class TokenBucket:
    """A thread-safe token bucket.

    Tokens refill continuously at ``rate`` tokens per ``per`` seconds up to ``capacity``.
    For the API-Football free tier use ``TokenBucket(capacity=10, refill_rate=10, per=60.0)``.
    """

    def __init__(
        self,
        capacity: int,
        refill_rate: float,
        per: float = 60.0,
        *,
        _now=time.monotonic,
    ) -> None:
        if capacity <= 0:
            raise ValueError("capacity must be positive")
        if refill_rate <= 0 or per <= 0:
            raise ValueError("refill_rate and per must be positive")
        self.capacity = capacity
        self._tokens = float(capacity)
        self._tokens_per_second = refill_rate / per
        self._now = _now
        self._timestamp = _now()
        self._lock = threading.Lock()

    def _refill_locked(self) -> None:
        now = self._now()
        elapsed = now - self._timestamp
        if elapsed > 0:
            self._tokens = min(
                self.capacity, self._tokens + elapsed * self._tokens_per_second
            )
            self._timestamp = now

    @property
    def tokens(self) -> float:
        """Current token count (refilled to now)."""
        with self._lock:
            self._refill_locked()
            return self._tokens

    def try_acquire(self, amount: int = 1) -> bool:
        """Take ``amount`` tokens without blocking. Return True on success."""
        with self._lock:
            self._refill_locked()
            if self._tokens >= amount:
                self._tokens -= amount
                return True
            return False

    def acquire(self, amount: int = 1, timeout: float | None = None) -> bool:
        """Block until ``amount`` tokens are available or ``timeout`` elapses.

        Returns True if acquired, False if it timed out.
        """
        deadline = None if timeout is None else self._now() + timeout
        while True:
            with self._lock:
                self._refill_locked()
                if self._tokens >= amount:
                    self._tokens -= amount
                    return True
                needed = amount - self._tokens
                wait = needed / self._tokens_per_second
            if deadline is not None:
                remaining = deadline - self._now()
                if remaining <= 0:
                    return False
                wait = min(wait, remaining)
            time.sleep(max(wait, 0.0))


# The process-wide shared budget. All agents acquire from this before an API-Football call.
shared_budget = TokenBucket(capacity=10, refill_rate=10, per=60.0)
