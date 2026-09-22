"""The job row: frozen, final states named, the outcome carried separately from the state."""

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest

from catalyst_ai.platform.ids import new_id
from catalyst_ai.platform.storage import JobRow
from catalyst_ai.platform.storage.jobrows import FINAL, QUEUED, RUNNING
from tools import origin

NOW = datetime(2026, 9, 25, 9, 0, tzinfo=UTC)


def test_the_row_is_frozen_and_the_final_states_are_the_contracts() -> None:
    row = JobRow(
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
    with pytest.raises(dataclasses.FrozenInstanceError):
        JobRow.__setattr__(row, "state", RUNNING)
    assert frozenset({"succeeded", "failed", "expired", "quarantined"}) == FINAL
    assert QUEUED not in FINAL
    done = row.finished("quarantined", NOW, NOW + timedelta(days=1)).with_outcome(
        reason="malformed"
    )
    assert done.state == "quarantined"
    assert done.finished_at == NOW
    assert done.quarantine_reason == "malformed"
    assert done.result is None
    assert row.state == QUEUED
