"""The fault transport follows its script and repeats the last entry."""

import httpx
import pytest

from catalyst_ai.providers.faults import Fault, FaultTransport


async def test_script_is_consumed_then_repeats() -> None:
    transport = FaultTransport([Fault(status=500), Fault(status=200, body={"ok": 1})])
    async with httpx.AsyncClient(transport=transport, timeout=1.0) as client:
        first = await client.get("http://p/")
        second = await client.get("http://p/")
        third = await client.get("http://p/")
    assert (first.status_code, second.status_code, third.status_code) == (500, 200, 200)
    assert transport.calls == 3


async def test_script_can_raise() -> None:
    transport = FaultTransport([Fault(raises=httpx.ConnectError)])
    async with httpx.AsyncClient(transport=transport, timeout=1.0) as client:
        with pytest.raises(httpx.ConnectError):
            await client.get("http://p/")


def test_empty_script_is_refused() -> None:
    with pytest.raises(ValueError, match="at least one"):
        FaultTransport([])
