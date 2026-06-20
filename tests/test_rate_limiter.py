"""Token-bucket contract tests. See ../docs/api-football.md (rate-limit ruleset).

Uses an injectable clock so the bucket's refill behaviour is tested deterministically (no sleeps).
"""

from __future__ import annotations

from app.rate_limiter import TokenBucket


class FakeClock:
    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


def test_starts_full():
    clock = FakeClock()
    b = TokenBucket(capacity=10, refill_rate=10, per=60.0, _now=clock)
    assert b.tokens == 10


def test_try_acquire_consumes_tokens():
    clock = FakeClock()
    b = TokenBucket(capacity=10, refill_rate=10, per=60.0, _now=clock)
    for _ in range(10):
        assert b.try_acquire() is True
    # Budget exhausted: the 11th request in the same minute is refused.
    assert b.try_acquire() is False


def test_refills_over_time():
    clock = FakeClock()
    b = TokenBucket(capacity=10, refill_rate=10, per=60.0, _now=clock)
    assert b.try_acquire(10) is True
    assert b.try_acquire() is False
    # 10 tokens / 60s => 1 token every 6 seconds.
    clock.advance(6.0)
    assert b.try_acquire() is True
    assert b.try_acquire() is False


def test_does_not_exceed_capacity():
    clock = FakeClock()
    b = TokenBucket(capacity=10, refill_rate=10, per=60.0, _now=clock)
    clock.advance(3600.0)  # a long idle period
    assert b.tokens == 10


def test_invalid_construction():
    import pytest

    with pytest.raises(ValueError):
        TokenBucket(capacity=0, refill_rate=10)
    with pytest.raises(ValueError):
        TokenBucket(capacity=10, refill_rate=0)
