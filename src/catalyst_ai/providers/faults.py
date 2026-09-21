"""Fault injection: a transport that fails or answers on a script, for rehearsals and tests."""

import json
from collections import deque
from dataclasses import dataclass

import httpx


@dataclass(frozen=True)
class Fault:
    """One scripted outcome: an HTTP status with a body, or a transport exception to raise."""

    status: int = 200
    body: dict[str, object] | None = None
    raises: type[Exception] | None = None
    raw: str | None = None


INJECTED = "injected fault"


class FaultTransport(httpx.AsyncBaseTransport):
    """Answer each request with the next scripted fault; the last one repeats."""

    def __init__(self, script: list[Fault]) -> None:
        """Bind the script; an empty script is a defect."""
        if not script:
            message = "a fault script needs at least one entry"
            raise ValueError(message)
        self._script = deque(script)
        self.calls = 0

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Consume the script."""
        self.calls += 1
        fault = self._script.popleft() if len(self._script) > 1 else self._script[0]
        if fault.raises is not None:
            raise fault.raises(INJECTED)
        content = (
            fault.raw.encode() if fault.raw is not None else json.dumps(fault.body or {}).encode()
        )
        return httpx.Response(status_code=fault.status, content=content, request=request)
