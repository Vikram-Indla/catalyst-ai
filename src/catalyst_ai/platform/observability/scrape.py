"""The ops port's `/metrics`: the process's counters, plus the gauges read at scrape time.

The route is on the ops port only — never on the contract port, where the proof of origin
governs, and where a collector that signs nothing could not reach it anyway — and it carries no
content: every line is a metric name, id labels and a number. Only the worker's scrape reads
the queue: counting every organisation's jobs takes the maintenance role, which serve's login
does not hold.
"""

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse
from starlette.datastructures import State

from catalyst_ai.platform.observability.metrics import JOBS, Metrics
from catalyst_ai.platform.storage import JobStore, StorageUnavailableError
from catalyst_ai.platform.storage.jobrows import QUEUED, RUNNING

CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"
router = APIRouter(tags=["ops"], include_in_schema=False)


async def read_gauges(metrics: Metrics, jobs: JobStore) -> None:
    """Read what only the database knows: the queue's depth and what is running."""
    for state in (QUEUED, RUNNING):
        try:
            depth = await jobs.count_jobs(state)
        except StorageUnavailableError:
            _forget(metrics)
            return
        metrics.set_gauge(JOBS, float(depth), {"state": state})


async def _worker_gauges(state: State, metrics: Metrics) -> None:
    """Read the queue gauges on the worker's ops port only; serve's login cannot count them."""
    if getattr(state, "worker", None) is not None:
        await read_gauges(metrics, state.runtime.jobs)


def _forget(metrics: Metrics) -> None:
    """Drop the queue gauges: a depth nobody could read this time is not the depth now."""
    for state in (QUEUED, RUNNING):
        metrics.drop_gauge(JOBS, {"state": state})


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics(request: Request) -> PlainTextResponse:
    """Render the process's metrics for the collector to scrape."""
    registry: Metrics = request.app.state.metrics
    await _worker_gauges(request.app.state, registry)
    return PlainTextResponse(content=registry.render(), media_type=CONTENT_TYPE)
