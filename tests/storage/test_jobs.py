"""The jobs table against a real database: idempotency, RLS, SKIP LOCKED, the attacker's rows."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import asyncpg
import pytest
from pydantic import BaseModel

from catalyst_ai.platform.auth import KeyRegistry, body_hash
from catalyst_ai.platform.ids import new_id
from catalyst_ai.platform.jobs import Worker
from catalyst_ai.platform.observability import JOB_QUARANTINED, SecurityCounters
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.platform.storage import JobRow, PostgresJobStore, PostgresStorage
from catalyst_ai.platform.storage.jobrows import QUEUED
from tests.unit.capabilities.improve_story.conftest import (
    ScriptedProvider,
    make_runtime,
    make_settings,
)
from tools import origin

pytestmark = pytest.mark.enable_socket
CAP = "echo"
WINDOW_S = 3_600
RAW_INSERT = (
    "INSERT INTO jobs (id, organization_id, capability, request_hash, envelope, payload,"
    " payload_hash, state, attempts, job_expires_at, created_at)"
    " VALUES ($1, $2, $3, $4, $5, $6, $7, 'queued', 0, $8, now())"
)
RAW_STATE = "SELECT state, result FROM jobs WHERE id = $1"
ATTACK = b"attack"


class Echo(BaseModel):
    text: str


async def _echo(payload: bytes, _runtime: RuntimeContext, _request_id: str) -> BaseModel:
    return Echo(text=payload.decode())


def _row(organization_id: UUID, payload: bytes, signer: origin.Signer) -> JobRow:
    now = datetime.now(tz=UTC)
    job_exp = int(now.timestamp()) + WINDOW_S
    return JobRow(
        id=new_id(),
        organization_id=organization_id,
        capability=CAP,
        request_hash=body_hash(payload),
        envelope=signer.sign(organization_id, CAP, payload, job_exp=job_exp),
        payload=payload,
        payload_hash=body_hash(payload),
        state=QUEUED,
        attempts=0,
        job_expires_at=job_exp,
        created_at=now,
    )


def _attack(
    organization_id: UUID, request_hash: str, envelope: str, payload: bytes, job_exp: int
) -> JobRow:
    """A row the way a database writer would insert it: no door, no verification."""
    return JobRow(
        id=new_id(),
        organization_id=organization_id,
        capability=CAP,
        request_hash=request_hash,
        envelope=envelope,
        payload=payload,
        payload_hash=body_hash(ATTACK),
        state=QUEUED,
        attempts=0,
        job_expires_at=job_exp,
        created_at=datetime.now(tz=UTC),
    )


def _worker(runtime: RuntimeContext, store: PostgresJobStore) -> tuple[Worker, SecurityCounters]:
    counters = SecurityCounters()
    keys = KeyRegistry.from_config(origin.PUBLIC_KEYS)
    return Worker(runtime, store, {CAP: _echo}, keys, counters), counters


async def _raw_insert(database_url: str, row: JobRow) -> None:
    connection = await asyncpg.connect(database_url, timeout=5)
    try:
        await connection.execute(
            RAW_INSERT,
            row.id,
            row.organization_id,
            row.capability,
            row.request_hash,
            row.envelope,
            row.payload,
            row.payload_hash,
            row.job_expires_at,
        )
    finally:
        await connection.close()


async def _raw_state(database_url: str, job_id: UUID) -> tuple[str, str | None]:
    connection = await asyncpg.connect(database_url, timeout=5)
    try:
        record = await connection.fetchrow(RAW_STATE, job_id)
    finally:
        await connection.close()
    assert record is not None
    return record["state"], record["result"]


async def test_create_is_idempotent_and_reads_are_bound_by_the_tenant(
    storage: PostgresStorage,
) -> None:
    store = PostgresJobStore(storage)
    a, b = uuid4(), uuid4()
    signer = origin.Signer()
    row = await store.create_job(_row(a, b"same", signer))
    again = await store.create_job(_row(a, b"same", signer))
    assert again.id == row.id
    theirs = await store.create_job(_row(b, b"same", signer))
    assert theirs.id != row.id
    assert await store.read_job(a, row.id) is not None
    assert await store.read_job(b, row.id) is None
    assert await store.read_job(a, uuid4()) is None
    await store.finish_job(row.finished("failed", datetime.now(tz=UTC), datetime.now(tz=UTC)))
    await store.finish_job(theirs.finished("failed", datetime.now(tz=UTC), datetime.now(tz=UTC)))
    assert await store.purge_jobs(datetime.now(tz=UTC) + timedelta(seconds=1)) >= 2


async def test_concurrent_claims_take_different_rows_under_the_bound(
    storage: PostgresStorage,
) -> None:
    store = PostgresJobStore(storage)
    a, b = uuid4(), uuid4()
    signer = origin.Signer()
    rows = [
        await store.create_job(_row(o, t, signer)) for o, t in ((a, b"1"), (a, b"2"), (b, b"3"))
    ]
    now = datetime.now(tz=UTC)
    claims = await asyncio.gather(*(store.claim_job(now, 1) for _ in range(3)))
    taken = [c for c in claims if c is not None]
    assert len(taken) == 2
    assert {c.organization_id for c in taken} == {a, b}
    assert all(c.state == "running" and c.attempts == 1 for c in taken)
    assert await store.count_jobs("running") >= 2
    await store.requeue_job(taken[0].organization_id, taken[0].id)
    requeued = await store.read_job(taken[0].organization_id, taken[0].id)
    assert requeued is not None
    assert requeued.state == "queued"
    until = datetime.now(tz=UTC)
    for row in rows:
        await store.finish_job(row.finished("expired", until, until))
    assert await store.purge_jobs(until + timedelta(seconds=1)) >= 3


async def test_the_attackers_rows_inserted_into_the_database_are_quarantined_on_the_real_loop(
    storage: PostgresStorage, database_url: str
) -> None:
    store = PostgresJobStore(storage)
    runtime = make_runtime(ScriptedProvider([]), make_settings())
    signer = origin.Signer(clock=runtime.clock)
    forged = origin.Signer(origin.SECOND_SEED, origin.KEY_ID, runtime.clock)
    a, b = uuid4(), uuid4()
    legitimate = await store.create_job(_row(a, b"ok", signer))
    job_exp = legitimate.job_expires_at
    good = signer.sign(a, CAP, ATTACK, job_exp=job_exp)
    rows = {
        "no_envelope": _attack(a, "h1", "", ATTACK, job_exp),
        "made_up": _attack(a, "h2", "Catalyst-Envelope x.y", ATTACK, job_exp),
        "other_org": _attack(b, "h3", good, ATTACK, job_exp),
        "edited_payload": _attack(a, "h4", good, ATTACK + b"!", job_exp),
        "forged_key": _attack(
            a, "h5", forged.sign(a, CAP, ATTACK, job_exp=job_exp), ATTACK, job_exp
        ),
        "past_window": _attack(a, "h6", signer.sign(a, CAP, ATTACK, job_exp=1), ATTACK, 1),
    }
    for row in rows.values():
        await _raw_insert(database_url, row)
    worker, counters = _worker(runtime, store)
    stop = asyncio.Event()
    serving = asyncio.create_task(worker.serve(stop))
    await asyncio.sleep(2)
    stop.set()
    await asyncio.wait_for(serving, timeout=10)
    for name, row in rows.items():
        state, result = await _raw_state(database_url, row.id)
        expected = "expired" if name == "past_window" else "quarantined"
        assert state == expected, name
        assert result is None, name
    assert counters.value(JOB_QUARANTINED) == 5
    state, result = await _raw_state(database_url, legitimate.id)
    assert state == "succeeded"
    assert result == '{"text":"ok"}'
    until = datetime.now(tz=UTC) + timedelta(seconds=1)
    assert await store.purge_jobs(until) >= 7
