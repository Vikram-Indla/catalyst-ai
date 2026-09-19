"""Tenant caps: the daily counter refuses at the line; slots bound concurrency per organisation."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.budgets import TenantBudgets
from catalyst_ai.platform.errors import Error


class FrozenClock:
    def __init__(self, at: datetime) -> None:
        self.at = at

    def now(self) -> datetime:
        return self.at


def _budgets(cap: int = 100, concurrency: int = 1) -> tuple[TenantBudgets, FrozenClock]:
    clock = FrozenClock(datetime(2026, 9, 18, 12, 0, tzinfo=UTC))
    return TenantBudgets(clock, cap, concurrency), clock


def test_reserve_refuses_over_the_cap_with_retry_after() -> None:
    budgets, _ = _budgets(cap=100)
    org = uuid4()
    budgets.reserve(org, 60)
    budgets.settle(org, 60)
    with pytest.raises(Error) as caught:
        budgets.reserve(org, 50)
    assert caught.value.code is ErrorCode.BUDGET_EXCEEDED
    assert caught.value.retry_after_ms == 12 * 3600 * 1000


def test_window_rolls_over_at_midnight() -> None:
    budgets, clock = _budgets(cap=100)
    org = uuid4()
    budgets.settle(org, 100)
    assert budgets.spent_today(org) == 100
    clock.at = clock.at + timedelta(days=1)
    assert budgets.spent_today(org) == 0
    budgets.reserve(org, 100)


def test_organisations_do_not_share_a_counter() -> None:
    budgets, _ = _budgets(cap=100)
    first, second = uuid4(), uuid4()
    budgets.settle(first, 100)
    budgets.reserve(second, 100)


async def test_slot_bounds_concurrency() -> None:
    budgets, _ = _budgets(concurrency=1)
    org = uuid4()
    peak = 0
    running = 0

    async def work() -> None:
        nonlocal peak, running
        async with budgets.slot(org):
            running += 1
            peak = max(peak, running)
            await asyncio.sleep(0)
            running -= 1

    await asyncio.gather(work(), work(), work())
    assert peak == 1
