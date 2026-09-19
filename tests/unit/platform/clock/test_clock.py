"""SystemClock returns aware UTC time."""

from datetime import UTC

from catalyst_ai.platform.clock import Clock, SystemClock


def test_system_clock_is_utc() -> None:
    clock: Clock = SystemClock()
    assert clock.now().tzinfo is UTC
