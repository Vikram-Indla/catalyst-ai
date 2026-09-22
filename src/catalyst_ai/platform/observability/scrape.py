"""The ops port's `/metrics`: the process's counters, plus the gauges read at scrape time.

The route is on the ops port only — never on the contract port, where the proof of origin
governs — and it carries no content: every line is a metric name, id labels and a number.
"""

from fastapi import APIRouter, Request
from fastapi.responses import PlainTextResponse

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
            return
        metrics.set_gauge(JOBS, float(depth), {"state": state})


@router.get("/metrics", response_class=PlainTextResponse)
async def metrics(request: Request) -> PlainTextResponse:
    """Render the process's metrics for the collector to scrape."""
    registry: Metrics = request.app.state.metrics
    await read_gauges(registry, request.app.state.runtime.jobs)
    return PlainTextResponse(content=registry.render(), media_type=CONTENT_TYPE)
