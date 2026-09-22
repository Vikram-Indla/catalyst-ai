"""The in-memory job store: the seam's contract without a database."""

from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from catalyst_ai.platform.ids import new_id
from catalyst_ai.platform.storage import JobRow, MemoryJobStore
from catalyst_ai.platform.storage.jobrows import QUEUED

A = UUID("11111111-1111-7111-8111-111111111111")
B = UUID("22222222-2222-7222-8222-222222222222")
NOW = datetime(2026, 9, 25, 9, 0, tzinfo=UTC)


def _row(organization_id: UUID, request_hash: str, at: datetime = NOW) -> JobRow:
    return JobRow(
        id=new_id(),
        organization_id=organization_id,
        capability="documents",
        request_hash=request_hash,
        envelope="e",
        payload=b"{}",
        payload_hash=request_hash,
        state=QUEUED,
        attempts=0,
        job_expires_at=1,
        created_at=at,
    )


async def test_create_is_idempotent_per_organisation_and_reads_are_bound() -> None:
    store = MemoryJobStore()
    first = await store.create_job(_row(A, "h"))
    assert (await store.create_job(_row(A, "h"))).id == first.id
    theirs = await store.create_job(_row(B, "h"))
    assert theirs.id != first.id
    assert await store.read_job(A, first.id) is not None
    assert await store.read_job(B, first.id) is None
    assert await store.read_job(A, uuid4()) is None
    assert await store.count_jobs("queued") == 2
    assert await store.count_jobs("queued", A) == 1


async def test_claim_is_oldest_first_under_the_bound_and_requeue_returns_a_row() -> None:
    store = MemoryJobStore()
    older = await store.create_job(_row(A, "1", NOW - timedelta(minutes=1)))
    await store.create_job(_row(A, "2"))
    other = await store.create_job(_row(B, "3"))
    first = await store.claim_job(NOW, 1)
    assert first is not None
    assert first.id == older.id
    assert first.state == "running"
    assert first.attempts == 1
    second = await store.claim_job(NOW, 1)
    assert second is not None
    assert second.id == other.id
    assert await store.claim_job(NOW, 1) is None
    await store.requeue_job(B, first.id)
    assert (await store.read_job(A, first.id) or first).state == "running"
    await store.requeue_job(A, first.id)
    requeued = await store.read_job(A, first.id)
    assert requeued is not None
    assert requeued.state == "queued"
    assert requeued.started_at is None


async def test_finish_and_purge_by_result_expiry() -> None:
    store = MemoryJobStore()
    row = await store.create_job(_row(A, "h"))
    done = row.finished("succeeded", NOW, NOW + timedelta(hours=1)).with_outcome(result="{}")
    await store.finish_job(done)
    assert await store.purge_jobs(NOW + timedelta(minutes=30)) == 0
    assert await store.purge_jobs(NOW + timedelta(hours=2)) == 1
    assert await store.read_job(A, row.id) is None
    planted = _row(B, "p")
    store.plant(planted)
    assert await store.read_job(B, planted.id) is not None
