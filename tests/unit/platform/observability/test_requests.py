"""Request metrics: the status class, and one count and one duration per operation."""

import httpx
from fastapi import FastAPI

from catalyst_ai.platform.clock import SystemClock
from catalyst_ai.platform.observability import Metrics, RequestMetricsMiddleware
from catalyst_ai.platform.observability.metrics import REQUEST_SECONDS, REQUESTS
from catalyst_ai.platform.observability.requests import UNKNOWN, status_class


def test_status_class_is_the_family_not_the_code() -> None:
    assert status_class(200) == "2xx"
    assert status_class(404) == "4xx"
    assert status_class(503) == "5xx"


async def test_every_request_is_counted_under_its_operation_and_timed() -> None:
    app = FastAPI()
    metrics = Metrics()

    @app.get("/ok", operation_id="probe.ok")
    async def ok() -> dict[str, str]:
        return {"ok": "yes"}

    app.add_middleware(RequestMetricsMiddleware, metrics=metrics, clock=SystemClock())
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as client:
        assert (await client.get("/ok")).status_code == 200
        assert (await client.get("/nowhere")).status_code == 404
    assert metrics.value(REQUESTS, {"operation": "probe.ok", "status": "2xx"}) == 1
    assert metrics.value(REQUESTS, {"operation": UNKNOWN, "status": "4xx"}) == 1
    assert metrics.histogram(REQUEST_SECONDS, {"operation": "probe.ok"}).count == 1
