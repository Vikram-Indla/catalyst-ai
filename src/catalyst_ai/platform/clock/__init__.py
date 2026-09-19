"""The injected clock; nothing else reads the time."""

from catalyst_ai.platform.clock.clock import Clock, SystemClock

__all__ = ["Clock", "SystemClock"]
