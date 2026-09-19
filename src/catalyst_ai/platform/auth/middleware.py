"""Constant-time bearer-token check before any route; health routes are exempt."""

import hmac
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from pydantic import SecretStr
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.httpserver import render_error

BEARER = "Bearer "
EXEMPT_PATHS = frozenset({"/healthz", "/readyz"})


def verify_token(header: str | None, tokens: list[SecretStr]) -> bool:
    """Compare the presented bearer token against every configured token in constant time."""
    if header is None or not header.startswith(BEARER):
        return False
    presented = header.removeprefix(BEARER).encode()
    return any(
        hmac.compare_digest(presented, token.get_secret_value().encode()) for token in tokens
    )


class ServiceTokenMiddleware(BaseHTTPMiddleware):
    """Reject any non-exempt request without a valid service token."""

    def __init__(self, app: ASGIApp, tokens: list[SecretStr]) -> None:
        """Hold the configured tokens."""
        super().__init__(app)
        self._tokens = tokens

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Verify, then continue; render the envelope on failure."""
        if request.url.path in EXEMPT_PATHS or verify_token(
            request.headers.get("authorization"), self._tokens
        ):
            return await call_next(request)
        error = Error(ErrorCode.AUTH_INVALID, "a valid service token is required")
        return render_error(request, error)
