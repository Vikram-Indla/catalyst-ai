"""Submitting a job from the verified request path, and reading one back as the contract's status.

The row stores the envelope exactly as the door verified it (the backend's signature — the
service re-signs nothing) and the hash the envelope's `bh` covered; the request hash is that
same hash, so the same body from the same organisation is the same job (`INV-028`).
"""

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse

from catalyst_ai.contract.errors import ErrorBody, ErrorCode
from catalyst_ai.contract.jobs import FINAL_STATES, JobAccepted, JobState, JobStatus
from catalyst_ai.platform.auth import Envelope, envelope_of
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.httpserver import request_id_of
from catalyst_ai.platform.ids import new_id
from catalyst_ai.platform.observability import ORIGIN_REFUSED, Where, security_event
from catalyst_ai.platform.storage import JobStore
from catalyst_ai.platform.storage.jobrows import QUEUED, JobRow

LOCATION = "/v1/jobs/{id}"
RETRY_AFTER_MS = 2_000
NO_WINDOW = "no_job_window"
REFUSED_MESSAGE = "proof of origin required"


def _proven(request: Request) -> Envelope:
    envelope = envelope_of(request)
    if envelope is None or envelope.job_expires_at is None:
        counters = request.app.state.security
        where = Where(request_id_of(request), None, None)
        security_event(counters, ORIGIN_REFUSED, NO_WINDOW, where)
        raise Error(ErrorCode.AUTH_ORIGIN_INVALID, REFUSED_MESSAGE)
    return envelope


async def submit(
    request: Request, capability: str, jobs: JobStore, now: datetime
) -> tuple[JobAccepted, str]:
    """Store the verified request as a row and return the acceptance with its location."""
    envelope = _proven(request)
    body = await request.body()
    row = JobRow(
        id=new_id(),
        organization_id=envelope.organization_id,
        capability=capability,
        request_hash=envelope.body_hash,
        envelope=str(request.headers.get("authorization")),
        payload=body,
        payload_hash=envelope.body_hash,
        state=QUEUED,
        attempts=0,
        job_expires_at=envelope.job_expires_at or 0,
        created_at=now,
    )
    stored = await jobs.create_job(row)
    accepted = JobAccepted(
        job_id=stored.id,
        state=JobState(stored.state),
        capability=stored.capability,
        retry_after_ms=RETRY_AFTER_MS,
        request_id=request_id_of(request),
    )
    return accepted, LOCATION.format(id=stored.id)


def accepted_response(accepted: JobAccepted, location: str) -> JSONResponse:
    """Render `202` with the `Location` and `Retry-After` the backend polls by."""
    return JSONResponse(
        status_code=202,
        content=accepted.model_dump(mode="json"),
        headers={"Location": location, "Retry-After": str(RETRY_AFTER_MS // 1000)},
    )


def _loads(text: str | None) -> dict[str, Any] | None:
    if text is None:
        return None
    loaded = json.loads(text)
    return loaded if isinstance(loaded, dict) else None


def status_of(row: JobRow, request_id: str) -> JobStatus:
    """Render a row as the contract's status; `expired` and `quarantined` say nothing more."""
    state = JobState(row.state)
    final = state in FINAL_STATES
    error = _loads(row.error) if state is JobState.FAILED else None
    return JobStatus(
        job_id=row.id,
        capability=row.capability,
        state=state,
        attempts=row.attempts,
        created_at=row.created_at,
        started_at=row.started_at,
        finished_at=row.finished_at,
        retry_after_ms=None if final else RETRY_AFTER_MS,
        result=_loads(row.result) if state is JobState.SUCCEEDED else None,
        error=ErrorBody.model_validate(error) if error is not None else None,
        request_id=request_id,
    )


async def read(request: Request, jobs: JobStore, organization_id: UUID, job_id: UUID) -> JobRow:
    """Return the organisation's row, or `404` for any other organisation's or an unknown id."""
    envelope = envelope_of(request)
    row = await jobs.read_job(organization_id, job_id)
    if envelope is None or envelope.organization_id != organization_id or row is None:
        raise Error(ErrorCode.JOB_NOT_FOUND, "no such job")
    return row
