"""The in-process cache expires by the injected clock; a zero TTL stores nothing."""

from datetime import UTC, datetime, timedelta

from catalyst_ai.platform.cache import MemoryCache


class FrozenClock:
    def __init__(self) -> None:
        self.at = datetime(2026, 9, 18, tzinfo=UTC)

    def now(self) -> datetime:
        return self.at


def test_get_set_and_expiry() -> None:
    clock = FrozenClock()
    cache = MemoryCache(clock)
    assert cache.get("k") is None
    cache.set("k", "v", 10)
    assert cache.get("k") == "v"
    clock.at += timedelta(seconds=10)
    assert cache.get("k") is None
    assert cache.get("k") is None


def test_zero_ttl_stores_nothing() -> None:
    cache = MemoryCache(FrozenClock())
    cache.set("k", "v", 0)
    assert cache.get("k") is None
