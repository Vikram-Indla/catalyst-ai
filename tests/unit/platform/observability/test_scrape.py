"""The scrape: the process's counters plus the queue gauges, and never a failed scrape."""

from datetime import datetime
from uuid import UUID

import httpx
from fastapi import FastAPI

from catalyst_ai.platform.ids import new_id
from catalyst_ai.platform.observability import Metrics, metrics_router
from catalyst_ai.platform.observability.metrics import JOBS, ORIGIN_REFUSED
from catalyst_ai.platform.observability.scrape import CONTENT_TYPE, read_gauges
from catalyst_ai.platform.storage import JobRow, MemoryJobStore, StorageUnavailableError
from catalyst_ai.platform.storage.jobrows import QUEUED
from tools import origin


class _DownStore(MemoryJobStore):
    async def count_jobs(self, state: str, organization_id: UUID | None = None) -> int:
        raise StorageUnavailableError("ConnectionRefusedError")


def _row() -> JobRow:
    return JobRow(
        id=new_id(),
        organization_id=origin.ORG,
        capability="documents",
        request_hash="h",
        envelope="e",
        payload=b"{}",
        payload_hash="h",
        state=QUEUED,
        attempts=0,
        job_expires_at=1,
        created_at=datetime.now(tz=None).astimezone(),
    )


async def _client(metrics: Metrics, jobs: object) -> httpx.AsyncClient:
    app = FastAPI()
    app.include_router(metrics_router)
    app.state.metrics = metrics
    app.state.runtime = type("R", (), {"jobs": jobs})()
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://ops")


async def test_the_scrape_renders_the_counters_and_the_queue_depth() -> None:
    metrics = Metrics()
    metrics.count(ORIGIN_REFUSED, {"reason": "expired"})
    store = MemoryJobStore()
    await store.create_job(_row())
    async with await _client(metrics, store) as client:
        response = await client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"] == CONTENT_TYPE
    assert 'catalyst_ai_origin_refused_total{reason="expired"} 1' in response.text
    assert 'catalyst_ai_jobs{state="queued"} 1' in response.text
    assert 'catalyst_ai_jobs{state="running"} 0' in response.text


async def test_a_database_that_does_not_answer_leaves_the_gauges_out() -> None:
    metrics = Metrics()
    await read_gauges(metrics, _DownStore())
    assert metrics.value(JOBS, {"state": "queued"}) == 0
    async with await _client(metrics, _DownStore()) as client:
        response = await client.get("/metrics")
    assert response.status_code == 200
    assert "catalyst_ai_jobs" not in response.text


async def test_a_depth_read_before_an_outage_does_not_survive_the_failed_read() -> None:
    metrics = Metrics()
    store = MemoryJobStore()
    await store.create_job(_row())
    await read_gauges(metrics, store)
    assert 'catalyst_ai_jobs{state="queued"} 1' in metrics.render()
    await read_gauges(metrics, _DownStore())
    assert "catalyst_ai_jobs" not in metrics.render()
