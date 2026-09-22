"""The status a row renders as: retry-after until final; a final state says only what it may."""

import json
from datetime import UTC, datetime, timedelta

from catalyst_ai.contract.jobs import JobState
from catalyst_ai.platform.ids import new_id
from catalyst_ai.platform.jobs import status_of
from catalyst_ai.platform.jobs.submit import RETRY_AFTER_MS
from catalyst_ai.platform.storage import JobRow
from catalyst_ai.platform.storage.jobrows import QUEUED
from tools import origin

NOW = datetime(2026, 9, 24, 12, 0, tzinfo=UTC)


def _queued() -> JobRow:
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
        created_at=NOW,
    )


def _final(state: str, *, result: str | None = None, error: str | None = None) -> JobRow:
    row = _queued().finished(state, NOW + timedelta(seconds=5), NOW + timedelta(days=1))
    return row.with_outcome(result=result, error=error, reason="bad_signature")


def test_a_queued_status_carries_retry_after_and_nothing_else() -> None:
    status = status_of(_queued(), "r1")
    assert status.state is JobState.QUEUED
    assert status.retry_after_ms == RETRY_AFTER_MS
    assert status.result is None
    assert status.error is None
    assert status.request_id == "r1"


def test_final_states_carry_their_result_or_error_and_quarantine_says_nothing() -> None:
    succeeded = status_of(_final("succeeded", result=json.dumps({"chunks": 2})), "r")
    assert succeeded.retry_after_ms is None
    assert succeeded.result == {"chunks": 2}
    error = json.dumps({"code": "ai.provider.timeout", "message": "late", "details": []})
    failed = status_of(_final("failed", error=error), "r")
    assert failed.error is not None
    assert failed.error.code == "ai.provider.timeout"
    quarantined = status_of(_final("quarantined"), "r")
    assert quarantined.state is JobState.QUARANTINED
    assert quarantined.error is None
    assert "bad_signature" not in quarantined.model_dump_json()
    expired = status_of(_final("expired"), "r")
    assert expired.result is None
    assert expired.error is None
    assert status_of(_final("succeeded", result="[1]"), "r").result is None
