"""A circuit breaker per provider and model: closed → open → half-open, by failure count."""

from datetime import datetime, timedelta
from enum import StrEnum

from catalyst_ai.platform.clock import Clock


class BreakerState(StrEnum):
    """The three states."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class BreakerOpenError(Exception):
    """The breaker refused the call; carries how long until a probe is allowed."""

    def __init__(self, retry_after_ms: int) -> None:
        """Name the wait."""
        super().__init__(f"circuit open; retry after {retry_after_ms} ms")
        self.retry_after_ms = retry_after_ms


class Breaker:
    """Open after `failure_threshold` consecutive failures; half-open after `open_seconds`."""

    def __init__(self, clock: Clock, failure_threshold: int, open_seconds: int) -> None:
        """Bind the clock and the thresholds."""
        self._clock = clock
        self._threshold = failure_threshold
        self._open_for = timedelta(seconds=open_seconds)
        self._failures = 0
        self._opened_at: datetime | None = None
        self.state = BreakerState.CLOSED

    def before_call(self) -> None:
        """Refuse while open; allow one probe once the open window has passed."""
        if self.state is BreakerState.CLOSED or self._opened_at is None:
            return
        remaining = self._opened_at + self._open_for - self._clock.now()
        if self.state is BreakerState.OPEN and remaining.total_seconds() > 0:
            raise BreakerOpenError(int(remaining.total_seconds() * 1000) or 1)
        self.state = BreakerState.HALF_OPEN

    def record_success(self) -> None:
        """Close the breaker."""
        self._failures = 0
        self._opened_at = None
        self.state = BreakerState.CLOSED

    def record_failure(self) -> None:
        """Count a failure; open at the threshold or on a failed probe."""
        self._failures += 1
        if self.state is BreakerState.HALF_OPEN or self._failures >= self._threshold:
            self.state = BreakerState.OPEN
            self._opened_at = self._clock.now()
