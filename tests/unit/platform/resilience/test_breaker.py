"""The breaker: closed until the threshold, open for the window, one probe when half-open."""

from datetime import UTC, datetime, timedelta

import pytest

from catalyst_ai.platform.resilience import Breaker, BreakerOpenError
from catalyst_ai.platform.resilience.breaker import BreakerState


class FrozenClock:
    def __init__(self) -> None:
        self.at = datetime(2026, 9, 18, tzinfo=UTC)

    def now(self) -> datetime:
        return self.at


def _state(breaker: Breaker) -> BreakerState:
    return breaker.state


def test_opens_at_threshold_and_half_opens_after_the_window() -> None:
    clock = FrozenClock()
    breaker = Breaker(clock, failure_threshold=2, open_seconds=30)
    breaker.before_call()
    breaker.record_failure()
    assert _state(breaker) is BreakerState.CLOSED
    breaker.record_failure()
    assert _state(breaker) is BreakerState.OPEN
    with pytest.raises(BreakerOpenError) as caught:
        breaker.before_call()
    assert 0 < caught.value.retry_after_ms <= 30_000
    clock.at += timedelta(seconds=30)
    breaker.before_call()
    assert _state(breaker) is BreakerState.HALF_OPEN
    breaker.record_failure()
    assert _state(breaker) is BreakerState.OPEN
    clock.at += timedelta(seconds=30)
    breaker.before_call()
    breaker.record_success()
    assert _state(breaker) is BreakerState.CLOSED
