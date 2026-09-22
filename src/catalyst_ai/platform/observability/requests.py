"""Request metrics: one count and one duration per operation and status class, nothing else."""

from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from catalyst_ai.platform.clock import Clock
from catalyst_ai.platform.observability.metrics import REQUEST_SECONDS, REQUESTS, Metrics

UNKNOWN = "unknown"
HUNDRED = 100


def status_class(status: int) -> str:
    """Return the status class (`2xx`, `4xx`, …); the exact code is the log's business."""
    return f"{status // HUNDRED}xx"


class RequestMetricsMiddleware(BaseHTTPMiddleware):
    """Count every request by operation and status class, and time it."""

    def __init__(self, app: Callable[..., Awaitable[None]], metrics: Metrics, clock: Clock) -> None:
        """Hold the registry and the clock the durations are measured against."""
        super().__init__(app)
        self._metrics = metrics
        self._clock = clock

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Time the response, then record it under the route's operation id."""
        started = self._clock.now()
        response = await call_next(request)
        route = request.scope.get("route")
        operation = getattr(route, "operation_id", None) or UNKNOWN
        labels = {"operation": operation}
        seconds = (self._clock.now() - started).total_seconds()
        self._metrics.count(REQUESTS, {**labels, "status": status_class(response.status_code)})
        self._metrics.observe(REQUEST_SECONDS, seconds, labels)
        return response
