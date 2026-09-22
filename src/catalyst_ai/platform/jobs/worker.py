"""The worker: claim a row, verify its stored proof again, run it under its deadline, finish it.

A row is never trusted for being in the table (`ARCH-009 §1`): before anything executes, the
envelope the API stored is verified against the row's organisation, capability and payload
hash — computed from the bytes about to run, never read from a column — and against the job
window. A failure is `quarantined` with its reason — a security
event, counted — and the payload is never parsed. The service never calls the backend: the
result waits in the row for the backend's poll.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable, Mapping
from datetime import datetime, timedelta

from pydantic import BaseModel

from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.auth import (
    Envelope,
    KeyRegistry,
    Quarantine,
    Refusal,
    StoredProof,
    body_hash,
    verify_stored,
)
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.observability import (
    JOB_QUARANTINED,
    SecurityCounters,
    Where,
    security_event,
)
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.platform.storage import JobStore
from catalyst_ai.platform.storage.jobrows import EXPIRED, FAILED, QUARANTINED, SUCCEEDED, JobRow

JobRunner = Callable[[bytes, RuntimeContext, str], Awaitable[BaseModel]]
log = logging.getLogger(__name__)
IDLE_SLEEP_S = 0.5


class Worker:
    """One process's loop over the jobs table, bounded per organisation and in total."""

    def __init__(
        self,
        runtime: RuntimeContext,
        jobs: JobStore,
        runners: Mapping[str, JobRunner],
        keys: KeyRegistry,
        counters: SecurityCounters,
    ) -> None:
        """Hold the runtime, the store, the capability runners, the keys and the counters."""
        self._runtime = runtime
        self._jobs = jobs
        self._runners = runners
        self._keys = keys
        self._counters = counters
        self._settings = runtime.settings
        self._running: dict[asyncio.Task[None], JobRow] = {}
        self.draining = False

    async def run_once(self) -> bool:
        """Claim and settle one row; return whether there was one."""
        row = await self._claim()
        if row is None:
            return False
        await self._settle(row)
        return True

    async def _claim(self) -> JobRow | None:
        now = self._runtime.clock.now()
        return await self._jobs.claim_job(now, self._settings.worker_concurrency_per_organization)

    async def _settle(self, row: JobRow) -> None:
        now_s = int(self._runtime.clock.now().timestamp())
        proof = StoredProof(
            row.envelope, row.organization_id, row.capability, body_hash(row.payload)
        )
        verdict = verify_stored(proof, self._keys, now_s)
        if isinstance(verdict, Envelope):
            await self._execute(row, verdict)
        elif verdict is Quarantine.JOB_EXPIRED:
            at, until = self._when()
            await self._jobs.finish_job(row.finished(EXPIRED, at, until))
        else:
            await self._quarantine(row, verdict)

    def _when(self) -> tuple[datetime, datetime]:
        at = self._runtime.clock.now()
        return at, at + timedelta(seconds=self._settings.job_result_ttl_seconds)

    async def _quarantine(self, row: JobRow, reason: Refusal | Quarantine) -> None:
        where = Where(str(row.id), row.capability, None)
        security_event(self._counters, JOB_QUARANTINED, reason.value, where)
        at, until = self._when()
        quarantined = row.finished(QUARANTINED, at, until).with_outcome(reason=reason.value)
        await self._jobs.finish_job(quarantined)

    async def _execute(self, row: JobRow, envelope: Envelope) -> None:
        request_id = str(row.id)
        outcome = await self._run(row, request_id)
        if isinstance(outcome, Error):
            await self._fail(row, outcome)
            return
        at, until = self._when()
        payload = outcome.model_dump_json(exclude_none=True)
        await self._jobs.finish_job(row.finished(SUCCEEDED, at, until).with_outcome(result=payload))
        log.info(
            "job succeeded",
            extra={"job_id": request_id, "capability": row.capability, "subject": envelope.subject},
        )

    async def _run(self, row: JobRow, request_id: str) -> BaseModel | Error:
        runner = self._runners.get(row.capability)
        if runner is None:
            return Error(ErrorCode.CAPABILITY_UNKNOWN, "no runner for the job's capability")
        outcome: BaseModel | Error
        try:
            async with asyncio.timeout(self._settings.job_timeout_seconds):
                outcome = await runner(row.payload, self._runtime, request_id)
        except Error as error:
            outcome = error
        except TimeoutError:
            outcome = Error(ErrorCode.PROVIDER_TIMEOUT, "the job passed its deadline")
        except Exception as error:
            log.exception("job runner raised", extra={"job_id": request_id})
            outcome = Error(ErrorCode.INTERNAL_ERROR, type(error).__name__)
        return outcome

    async def _fail(self, row: JobRow, error: Error) -> None:
        at, until = self._when()
        body = error.envelope(str(row.id)).error.model_dump_json(exclude_none=True)
        await self._jobs.finish_job(row.finished(FAILED, at, until).with_outcome(error=body))

    async def serve(self, stop: asyncio.Event) -> None:
        """Loop until told to stop, then drain: finish what runs inside the window or requeue it."""
        limit = asyncio.Semaphore(self._settings.worker_concurrency)
        while not stop.is_set():
            await limit.acquire()
            row = await self._claim()
            if row is None:
                limit.release()
                await _wait(stop, IDLE_SLEEP_S)
                continue
            task = asyncio.create_task(self._settle_then_free(row, limit))
            self._running[task] = row
            task.add_done_callback(self._forget)
        await self.drain()

    def _forget(self, task: asyncio.Task[None]) -> None:
        self._running.pop(task, None)

    async def _settle_then_free(self, row: JobRow, limit: asyncio.Semaphore) -> None:
        try:
            await self._settle(row)
        finally:
            limit.release()

    async def drain(self) -> None:
        """Wait for the running rows inside the window; requeue whatever still runs after it."""
        self.draining = True
        pending = dict(self._running)
        if not pending:
            return
        _done, still = await asyncio.wait(
            set(pending), timeout=self._settings.shutdown_drain_seconds
        )
        for task in still:
            task.cancel()
        for task in still:
            row = pending[task]
            await self._jobs.requeue_job(row.organization_id, row.id)


async def _wait(stop: asyncio.Event, seconds: float) -> None:
    try:
        async with asyncio.timeout(seconds):
            await stop.wait()
    except TimeoutError:
        return
