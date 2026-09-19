"""Bounded retries with exponential backoff and jitter for idempotent calls."""

import asyncio
import random
from collections.abc import Awaitable, Callable
from dataclasses import dataclass


@dataclass(frozen=True)
class RetryPolicy:
    """How many attempts, and how long to wait between them."""

    attempts: int = 3
    base_ms: int = 200
    max_ms: int = 2_000
    seed: int | None = None

    def rng(self) -> random.Random:
        """Return the generator for the jitter; seeded in tests, unseeded in production."""
        return random.Random(self.seed)  # noqa: S311 — jitter, not cryptography

    def delay_ms(self, attempt: int, rng: random.Random) -> int:
        """Exponential backoff with full jitter for the given attempt (0-based)."""
        ceiling = min(self.max_ms, self.base_ms * (2**attempt))
        return rng.randint(0, ceiling)


async def retry_async[T](
    call: Callable[[], Awaitable[T]],
    policy: RetryPolicy,
    retry_on: Callable[[Exception], bool],
    rng: random.Random,
) -> T:
    """Run the call up to `policy.attempts` times; the last failure propagates unchanged."""
    attempt = 0
    while True:
        try:
            return await call()
        except Exception as error:
            if attempt >= policy.attempts - 1 or not retry_on(error):
                raise
            await asyncio.sleep(policy.delay_ms(attempt, rng) / 1000)
            attempt += 1
