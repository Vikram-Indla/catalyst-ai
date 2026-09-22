"""The job row as it crosses the JobStore seam: the proof, the payload, the state, the times."""

from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

QUEUED = "queued"
RUNNING = "running"
SUCCEEDED = "succeeded"
FAILED = "failed"
EXPIRED = "expired"
QUARANTINED = "quarantined"
FINAL = frozenset({SUCCEEDED, FAILED, EXPIRED, QUARANTINED})


@dataclass(frozen=True)
class JobRow:
    """One queued unit of work: born from the verified request path, verified again to run."""

    id: UUID
    organization_id: UUID
    capability: str
    request_hash: str
    envelope: str
    payload: bytes
    payload_hash: str
    state: str
    attempts: int
    job_expires_at: int
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result_expires_at: datetime | None = None
    result: str | None = None
    error: str | None = None
    quarantine_reason: str | None = None

    def finished(self, state: str, at: datetime, result_expires_at: datetime) -> "JobRow":
        """Return the row in a final state; the outcome goes on with `with_outcome`."""
        return replace(self, state=state, finished_at=at, result_expires_at=result_expires_at)

    def with_outcome(
        self, *, result: str | None = None, error: str | None = None, reason: str | None = None
    ) -> "JobRow":
        """Return the row carrying its result, its error, or the reason it was quarantined."""
        return replace(self, result=result, error=error, quarantine_reason=reason)
