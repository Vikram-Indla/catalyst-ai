"""The job contract: the states, the acceptance, the status and what a final state carries."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from catalyst_ai.contract.errors import ErrorBody, ErrorCode
from catalyst_ai.contract.jobs import FINAL_STATES, JobAccepted, JobState, JobStatus


def test_the_states_and_which_are_final() -> None:
    assert frozenset({"succeeded", "failed", "expired", "quarantined"}) == FINAL_STATES
    assert JobState.QUEUED not in FINAL_STATES
    assert JobState.RUNNING not in FINAL_STATES


def test_acceptance_and_status_bounds() -> None:
    accepted = JobAccepted(
        job_id=uuid4(),
        state=JobState.QUEUED,
        capability="documents",
        retry_after_ms=2000,
        request_id="r",
    )
    assert accepted.state == "queued"
    with pytest.raises(ValidationError):
        JobAccepted(
            job_id=uuid4(),
            state=JobState.QUEUED,
            capability="x" * 65,
            retry_after_ms=1,
            request_id="r",
        )
    with pytest.raises(ValidationError):
        JobAccepted(
            job_id=uuid4(), state=JobState.QUEUED, capability="x", retry_after_ms=0, request_id="r"
        )
    status = JobStatus(
        job_id=uuid4(),
        capability="documents",
        state=JobState.FAILED,
        attempts=1,
        created_at=datetime.now(tz=UTC),
        error=ErrorBody(code=ErrorCode.PROVIDER_UNAVAILABLE, message="down", details=[]),
        request_id="r",
    )
    assert status.retry_after_ms is None
    assert status.result is None
    with pytest.raises(ValidationError):
        JobStatus.model_validate({**status.model_dump(mode="json"), "extra": 1})
