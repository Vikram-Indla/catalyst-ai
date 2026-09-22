"""Proof of origin before any route: the envelope is verified and bound, or the request is refused.

A pure ASGI layer: it reads the body once (the hash is bound to those bytes), verifies, and
hands the same bytes on. Health routes are exempt; everything else needs a verified envelope
whose organisation is the body's and whose capability is the route's.
"""

import json
from collections.abc import Callable, Iterator, MutableMapping, Sequence
from typing import Any
from urllib.parse import parse_qs
from uuid import UUID

from fastapi import APIRouter, FastAPI, Request
from fastapi.routing import APIRoute
from starlette.routing import BaseRoute, Match
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.auth.envelope import Envelope
from catalyst_ai.platform.auth.verifier import Binding, Refusal, Verifier
from catalyst_ai.platform.clock import Clock
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.httpserver import render_error, request_id_of
from catalyst_ai.platform.observability.security import (
    ORIGIN_REFUSED,
    SecurityCounters,
    Where,
    security_event,
)

EXEMPT_PATHS = frozenset({"/healthz", "/readyz"})
CAPABILITY_EXTRA = "x-capability"
ORGANIZATION_FIELD = "organization_id"
ENVELOPE_STATE = "envelope"
REFUSED_MESSAGE = "proof of origin required"
UNVERIFIABLE_MESSAGE = "proof of origin could not be checked; retry"
RETRY_MS = 2000
Lookup = Callable[[Scope], str | None]


def _operations(routes: Sequence[BaseRoute], prefix: str = "") -> Iterator[tuple[str, APIRoute]]:
    """Yield every operation with the prefix it is mounted under, through included routers."""
    for route in routes:
        if isinstance(route, APIRoute):
            yield prefix, route
            continue
        included = getattr(route, "original_router", None)
        context = getattr(route, "include_context", None)
        if isinstance(included, APIRouter):
            yield from _operations(included.routes, prefix + str(getattr(context, "prefix", "")))


def capability_of(app: FastAPI) -> Lookup:
    """Return a lookup from an HTTP scope to the capability its operation declares, or None."""

    def lookup(scope: Scope) -> str | None:
        path = str(scope.get("path", ""))
        for prefix, route in _operations(app.routes):
            if not path.startswith(prefix):
                continue
            inner = {**scope, "path": path.removeprefix(prefix)}
            if route.matches(inner)[0] is Match.FULL:
                capability = (route.openapi_extra or {}).get(CAPABILITY_EXTRA)
                return capability if isinstance(capability, str) else None
        return None

    return lookup


def organization_of(body: bytes, query: bytes = b"") -> UUID | None:
    """Return the tenant the body names — or, for a body-less request, the query string names."""
    try:
        if body:
            parsed = json.loads(body)
            value = parsed.get(ORGANIZATION_FIELD) if isinstance(parsed, dict) else None
        else:
            values = parse_qs(query.decode("ascii", errors="replace")).get(ORGANIZATION_FIELD, [])
            value = values[0] if len(values) == 1 else None
        return UUID(value) if isinstance(value, str) else None
    except ValueError:
        return None


async def _read_body(receive: Receive) -> bytes:
    chunks = []
    while True:
        message = await receive()
        chunks.append(message.get("body", b""))
        if not message.get("more_body", False):
            return b"".join(chunks)


def _replaying(body: bytes, receive: Receive) -> Receive:
    delivered = False

    async def replay() -> Message:
        nonlocal delivered
        if delivered:
            return await receive()
        delivered = True
        return {"type": "http.request", "body": body, "more_body": False}

    return replay


def _error_of(refusal: Refusal) -> Error:
    if refusal is Refusal.UNVERIFIABLE:
        return Error(
            ErrorCode.AUTH_ORIGIN_UNVERIFIABLE, UNVERIFIABLE_MESSAGE, retry_after_ms=RETRY_MS
        )
    return Error(ErrorCode.AUTH_ORIGIN_INVALID, REFUSED_MESSAGE)


def envelope_of(request: Request) -> Envelope | None:
    """Return the verified envelope the middleware attached, for audit and the job path."""
    attached = getattr(request.state, ENVELOPE_STATE, None)
    return attached if isinstance(attached, Envelope) else None


class OriginMiddleware:
    """Refuse every non-exempt request whose envelope does not prove and bind its origin."""

    def __init__(
        self,
        app: ASGIApp,
        verifier: Verifier,
        counters: SecurityCounters,
        clock: Clock,
        lookup: Lookup,
    ) -> None:
        """Hold the verifier, the counters, the clock and the route lookup."""
        self._app = app
        self._verifier = verifier
        self._counters = counters
        self._clock = clock
        self._lookup = lookup

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Verify, bind and continue; render the envelope on refusal."""
        if scope["type"] != "http" or scope["path"] in EXEMPT_PATHS:
            await self._app(scope, receive, send)
            return
        body = await _read_body(receive)
        request = Request(scope)
        organization = organization_of(body, scope.get("query_string", b""))
        binding = Binding(body, organization, self._lookup(scope))
        now = int(self._clock.now().timestamp())
        verdict = await self._verifier.verify(request.headers.get("authorization"), binding, now)
        if isinstance(verdict, Refusal):
            where = Where(request_id_of(request), binding.capability)
            security_event(self._counters, ORIGIN_REFUSED, verdict.value, where)
            await render_error(request, _error_of(verdict))(scope, receive, send)
            return
        state: MutableMapping[str, Any] = scope.setdefault("state", {})
        state[ENVELOPE_STATE] = verdict
        await self._app(scope, _replaying(body, receive), send)
