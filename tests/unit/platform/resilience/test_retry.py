"""Retries: bounded attempts, only for retryable failures, jittered delays within the ceiling."""

import random

import pytest

from catalyst_ai.platform.resilience import RetryPolicy, retry_async

BROKEN = "broken"


async def test_retries_then_succeeds() -> None:
    calls = 0

    async def flaky() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise ConnectionError
        return "ok"

    policy = RetryPolicy(attempts=3, base_ms=0, max_ms=0)
    result = await retry_async(
        flaky, policy, lambda e: isinstance(e, ConnectionError), random.Random(1)
    )
    assert result == "ok"
    assert calls == 3


async def test_non_retryable_propagates_at_once() -> None:
    calls = 0

    async def broken() -> str:
        nonlocal calls
        calls += 1
        raise ValueError(BROKEN)

    with pytest.raises(ValueError, match=BROKEN):
        await retry_async(
            broken, RetryPolicy(attempts=3, base_ms=0, max_ms=0), lambda _e: False, random.Random(1)
        )
    assert calls == 1


async def test_last_attempt_propagates() -> None:
    async def always() -> str:
        raise ConnectionError

    with pytest.raises(ConnectionError):
        await retry_async(
            always, RetryPolicy(attempts=2, base_ms=0, max_ms=0), lambda _e: True, random.Random(1)
        )


def test_delay_is_jittered_within_the_ceiling() -> None:
    policy = RetryPolicy(attempts=3, base_ms=100, max_ms=250)
    rng = random.Random(7)
    assert all(0 <= policy.delay_ms(0, rng) <= 100 for _ in range(20))
    assert all(0 <= policy.delay_ms(5, rng) <= 250 for _ in range(20))
