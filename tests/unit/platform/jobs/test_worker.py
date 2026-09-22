"""The worker's loop: the per-organisation bound, failures, the deadline, drain and requeue."""

import asyncio
from datetime import timedelta
from uuid import UUID

from pydantic import BaseModel

from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.auth import KeyRegistry, body_hash
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.ids import new_id
from catalyst_ai.platform.jobs import JobRunner, Worker
from catalyst_ai.platform.observability import SecurityCounters
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.platform.storage import MemoryJobStore
from catalyst_ai.platform.storage.jobrows import QUEUED, JobRow
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tools import origin

ORG = origin.ORG
OTHER = UUID("22222222-2222-7222-8222-222222222222")
CAP = "echo"
WINDOW_S = 3_600


class Echo(BaseModel):
    text: str


def _runtime(**overrides: object) -> RuntimeContext:
    settings = make_settings(**overrides)
    return make_runtime(ScriptedProvider([]), settings)


def _row(runtime: RuntimeContext, payload: bytes, organization_id: UUID = ORG) -> JobRow:
    now = runtime.clock.now()
    signer = origin.Signer(clock=runtime.clock)
    header = signer.sign(organization_id, CAP, payload, job_exp=int(now.timestamp()) + WINDOW_S)
    return JobRow(
        id=new_id(),
        organization_id=organization_id,
        capability=CAP,
        request_hash=body_hash(payload),
        envelope=header,
        payload=payload,
        payload_hash=body_hash(payload),
        state=QUEUED,
        attempts=0,
        job_expires_at=int(now.timestamp()) + WINDOW_S,
        created_at=now,
    )


async def _echo(payload: bytes, _runtime: RuntimeContext, _request_id: str) -> BaseModel:
    return Echo(text=payload.decode())


async def _boom(payload: bytes, _runtime: RuntimeContext, _request_id: str) -> BaseModel:
    if payload == b"catalog":
        raise Error(ErrorCode.PROVIDER_UNAVAILABLE, "down")
    message = "not a catalog error"
    raise RuntimeError(message)


async def _slow(payload: bytes, _runtime: RuntimeContext, _request_id: str) -> BaseModel:
    await asyncio.sleep(5)
    return Echo(text=payload.decode())


def _worker(
    runtime: RuntimeContext, runner: JobRunner
) -> tuple[Worker, MemoryJobStore, SecurityCounters]:
    store = MemoryJobStore()
    counters = SecurityCounters(runtime.metrics)
    keys = KeyRegistry.from_config(origin.PUBLIC_KEYS)
    worker = Worker(runtime, store, {CAP: runner}, keys, counters)
    return worker, store, counters


async def test_a_verified_row_runs_and_carries_its_result_and_expiry() -> None:
    runtime = _runtime(job_result_ttl_seconds=60)
    worker, store, _ = _worker(runtime, _echo)
    row = await store.create_job(_row(runtime, b"hello"))
    assert await worker.run_once() is True
    done = await store.read_job(ORG, row.id)
    assert done is not None
    assert done.state == "succeeded"
    assert done.attempts == 1
    assert done.result == '{"text":"hello"}'
    assert done.result_expires_at == runtime.clock.now() + timedelta(seconds=60)
    assert await store.purge_jobs(runtime.clock.now() + timedelta(seconds=61)) == 1
    assert await store.read_job(ORG, row.id) is None


async def test_a_failing_runner_fails_the_row_with_its_error_or_internal_error() -> None:
    runtime = _runtime()
    worker, store, _ = _worker(runtime, _boom)
    catalog = await store.create_job(_row(runtime, b"catalog"))
    other = await store.create_job(_row(runtime, b"other"))
    assert await worker.run_once() is True
    assert await worker.run_once() is True
    first = await store.read_job(ORG, catalog.id)
    second = await store.read_job(ORG, other.id)
    assert first is not None
    assert second is not None
    assert first.state == "failed"
    assert '"code":"ai.provider.unavailable"' in str(first.error)
    assert second.state == "failed"
    assert '"code":"internal.error"' in str(second.error)
    assert "not a catalog error" not in str(second.error)


async def test_an_unknown_capability_fails_and_the_deadline_is_enforced() -> None:
    runtime = _runtime(job_timeout_seconds=1)
    worker, store, _ = _worker(runtime, _slow)
    slow = await store.create_job(_row(runtime, b"slow"))
    assert await worker.run_once() is True
    timed_out = await store.read_job(ORG, slow.id)
    assert timed_out is not None
    assert timed_out.state == "failed"
    assert '"code":"ai.provider.timeout"' in str(timed_out.error)
    unknown_worker = Worker(
        runtime,
        store,
        {},
        KeyRegistry.from_config(origin.PUBLIC_KEYS),
        SecurityCounters(runtime.metrics),
    )
    row = await store.create_job(_row(runtime, b"nobody"))
    assert await unknown_worker.run_once() is True
    failed = await store.read_job(ORG, row.id)
    assert failed is not None
    assert '"code":"ai.capability.unknown"' in str(failed.error)


async def test_the_per_organisation_bound_holds_under_concurrency() -> None:
    runtime = _runtime(worker_concurrency=8, worker_concurrency_per_organization=1)
    worker, store, _ = _worker(runtime, _echo)
    for text in (b"a1", b"a2", b"b1"):
        await store.create_job(_row(runtime, text, OTHER if text.startswith(b"b") else ORG))
    first = await store.claim_job(runtime.clock.now(), 1)
    second = await store.claim_job(runtime.clock.now(), 1)
    third = await store.claim_job(runtime.clock.now(), 1)
    assert first is not None
    assert second is not None
    assert {first.organization_id, second.organization_id} == {ORG, OTHER}
    assert third is None
    await worker.run_once()


async def test_drain_finishes_inside_the_window_or_requeues() -> None:
    runtime = _runtime(shutdown_drain_seconds=1, worker_concurrency=2)
    worker, store, _ = _worker(runtime, _slow)
    row = await store.create_job(_row(runtime, b"slow"))
    stop = asyncio.Event()
    serving = asyncio.create_task(worker.serve(stop))
    await asyncio.sleep(0.2)
    assert await store.count_jobs("running") == 1
    stop.set()
    await asyncio.wait_for(serving, timeout=5)
    assert worker.draining is True
    requeued = await store.read_job(ORG, row.id)
    assert requeued is not None
    assert requeued.state == "queued"
    assert requeued.started_at is None


async def test_serve_idles_when_the_queue_is_empty_and_stops_on_request() -> None:
    runtime = _runtime()
    worker, store, _ = _worker(runtime, _echo)
    row = await store.create_job(_row(runtime, b"quick"))
    stop = asyncio.Event()
    serving = asyncio.create_task(worker.serve(stop))
    await asyncio.sleep(0.3)
    stop.set()
    await asyncio.wait_for(serving, timeout=5)
    done = await store.read_job(ORG, row.id)
    assert done is not None
    assert done.state == "succeeded"
