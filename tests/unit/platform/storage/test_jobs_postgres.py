"""The pure parts of PostgresJobStore: the queries load, and an unconnected store refuses."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from catalyst_ai.platform.storage import PostgresJobStore, PostgresStorage, StorageUnavailableError
from catalyst_ai.platform.storage.jobs_postgres import COLUMNS
from catalyst_ai.platform.storage.postgres import sql
from tests.unit.capabilities.improve_story.conftest import FrozenClock

QUERIES = ("job_insert", "job_by_hash", "job_read", "job_claim", "job_finish", "job_requeue")


def test_every_job_query_names_the_table_and_the_tenant() -> None:
    for name in (*QUERIES, "job_count", "job_organizations", "job_purge"):
        text = sql(name)
        assert "jobs" in text, name
        assert "organization_id" in text, name
    assert "FOR UPDATE SKIP LOCKED" in sql("job_claim")
    assert "ON CONFLICT (organization_id, request_hash) DO NOTHING" in sql("job_insert")
    for column in COLUMNS.split(", "):
        assert column in sql("job_read")


async def test_an_unconnected_store_refuses_every_operation() -> None:
    storage = PostgresStorage("postgresql://u:p@h/d", FrozenClock(), 2, 1.0)
    store = PostgresJobStore(storage)
    assert storage.pool is None
    with pytest.raises(StorageUnavailableError):
        await store.read_job(uuid4(), uuid4())
    with pytest.raises(StorageUnavailableError):
        await store.claim_job(datetime.now(tz=UTC), 1)
    with pytest.raises(StorageUnavailableError):
        await store.count_jobs("queued")
