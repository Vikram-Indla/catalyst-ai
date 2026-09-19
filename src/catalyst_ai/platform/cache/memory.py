"""The Cache seam and its in-process implementation; the storage-backed one arrives with storage."""

from datetime import timedelta
from typing import Protocol

from catalyst_ai.platform.clock import Clock


class Cache(Protocol):
    """Get and set opaque JSON text under a key with a time to live."""

    def get(self, key: str) -> str | None:
        """Return the value or None when absent or expired."""
        ...

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """Store the value for the time to live; zero stores nothing."""
        ...


class MemoryCache:
    """A per-process dictionary with expiry from the injected clock."""

    def __init__(self, clock: Clock) -> None:
        """Bind the clock."""
        self._clock = clock
        self._entries: dict[str, tuple[str, float]] = {}

    def get(self, key: str) -> str | None:
        """Return the value or None when absent or expired; expired entries are dropped."""
        entry = self._entries.get(key)
        if entry is None:
            return None
        value, expires_at = entry
        if self._clock.now().timestamp() >= expires_at:
            del self._entries[key]
            return None
        return value

    def set(self, key: str, value: str, ttl_seconds: int) -> None:
        """Store the value; a zero time to live stores nothing."""
        if ttl_seconds <= 0:
            return
        expires_at = (self._clock.now() + timedelta(seconds=ttl_seconds)).timestamp()
        self._entries[key] = (value, expires_at)
