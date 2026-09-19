"""The Clock seam and its system implementation."""

from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    """Where the current time comes from; tests substitute it."""

    def now(self) -> datetime:
        """Return the current UTC time."""
        ...


class SystemClock:
    """Return the wall clock."""

    def now(self) -> datetime:
        """Return the current UTC time from the system."""
        return datetime.now(tz=UTC)
