"""Spend and concurrency caps per organisation, counted here so a runaway trips before the bill."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import date
from uuid import UUID

from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.clock import Clock
from catalyst_ai.platform.errors import Error

SECONDS_PER_DAY = 86_400
MS_PER_SECOND = 1000


class TenantBudgets:
    """A rolling daily spend counter and a concurrency semaphore per organisation."""

    def __init__(self, clock: Clock, default_micros_per_day: int, concurrency_max: int) -> None:
        """Bind the caps; overrides per organisation arrive with the storage package."""
        self._clock = clock
        self._default = default_micros_per_day
        self._concurrency_max = concurrency_max
        self._spent: dict[tuple[UUID, date], int] = {}
        self._slots: dict[UUID, asyncio.Semaphore] = {}

    def _window(self, organization_id: UUID) -> tuple[UUID, date]:
        return organization_id, self._clock.now().date()

    def spent_today(self, organization_id: UUID) -> int:
        """Micro-dollars this organisation has spent in the current window."""
        return self._spent.get(self._window(organization_id), 0)

    def _retry_after_ms(self) -> int:
        now = self._clock.now()
        elapsed = now.hour * 3600 + now.minute * 60 + now.second
        return (SECONDS_PER_DAY - elapsed) * MS_PER_SECOND

    def reserve(self, organization_id: UUID, estimated_micros: int) -> None:
        """Refuse with `ai.budget.exceeded` when the estimate would cross the daily cap."""
        if self.spent_today(organization_id) + estimated_micros > self._default:
            raise Error(
                ErrorCode.BUDGET_EXCEEDED,
                "the organisation's daily budget is exhausted",
                retry_after_ms=self._retry_after_ms(),
            )

    def settle(self, organization_id: UUID, actual_micros: int) -> None:
        """Count what a call cost."""
        window = self._window(organization_id)
        self._spent[window] = self._spent.get(window, 0) + actual_micros

    @asynccontextmanager
    async def slot(self, organization_id: UUID) -> AsyncIterator[None]:
        """Hold one of the organisation's concurrent-call slots for the duration."""
        semaphore = self._slots.setdefault(
            organization_id, asyncio.Semaphore(self._concurrency_max)
        )
        async with semaphore:
            yield
