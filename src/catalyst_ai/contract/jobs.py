"""The job shapes: what a submission returns and what a poll reads (`ADR-007`)."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from catalyst_ai.contract.errors import ErrorBody

MAX_CAPABILITY = 64


class JobState(StrEnum):
    """Where a job is; the last four are final."""

    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    EXPIRED = "expired"
    QUARANTINED = "quarantined"


FINAL_STATES = frozenset(
    {JobState.SUCCEEDED, JobState.FAILED, JobState.EXPIRED, JobState.QUARANTINED}
)


class JobAccepted(BaseModel):
    """What a `:jobs` submission returns with `202` and `Location`."""

    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    state: JobState
    capability: Annotated[str, Field(max_length=MAX_CAPABILITY)]
    retry_after_ms: Annotated[int, Field(gt=0)]
    request_id: str


class JobStatus(BaseModel):
    """What `jobs.get` returns: the state, and the result or the error once the job is final.

    `expired` and `quarantined` carry no detail of why — the reason is the service's security
    log, never the caller's. The result is the capability's own response, whole.
    """

    model_config = ConfigDict(extra="forbid")

    job_id: UUID
    capability: Annotated[str, Field(max_length=MAX_CAPABILITY)]
    state: JobState
    attempts: Annotated[int, Field(ge=0)]
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    retry_after_ms: Annotated[int | None, Field(gt=0)] = None
    result: dict[str, Any] | None = None
    error: ErrorBody | None = None
    request_id: str
