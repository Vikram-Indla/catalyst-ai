"""The `jobs` table behind the JobStore seam: tenant reads under RLS, the claim under maintenance.

A claim is `SELECT … FOR UPDATE SKIP LOCKED` inside one transaction, so two workers never take
the same row; the per-organisation bound is a count inside the same statement.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any
from uuid import UUID

import asyncpg

from catalyst_ai.platform.storage.jobrows import JobRow
from catalyst_ai.platform.storage.postgres import (
    NOT_CONNECTED,
    PostgresStorage,
    StorageUnavailableError,
    sql,
)

COLUMNS = (
    "id, organization_id, capability, request_hash, envelope, payload, payload_hash, state, "
    "attempts, job_expires_at, created_at, started_at, finished_at, result_expires_at, "
    "result, error, quarantine_reason"
)


def _row_of(record: asyncpg.Record) -> JobRow:
    return JobRow(
        id=record["id"],
        organization_id=record["organization_id"],
        capability=record["capability"],
        request_hash=record["request_hash"],
        envelope=record["envelope"],
        payload=bytes(record["payload"]),
        payload_hash=record["payload_hash"],
        state=record["state"],
        attempts=int(record["attempts"]),
        job_expires_at=int(record["job_expires_at"]),
        created_at=record["created_at"],
        started_at=record["started_at"],
        finished_at=record["finished_at"],
        result_expires_at=record["result_expires_at"],
        result=record["result"],
        error=record["error"],
        quarantine_reason=record["quarantine_reason"],
    )


class PostgresJobStore:
    """The job rows of the service's own database, over the storage adapter's pool."""

    def __init__(self, storage: PostgresStorage) -> None:
        """Share the pool and the session rules of the storage adapter."""
        self._storage = storage

    @asynccontextmanager
    async def _maintenance(self) -> AsyncIterator[Any]:
        pool = self._storage.pool
        if pool is None:
            raise StorageUnavailableError(NOT_CONNECTED)
        try:
            async with pool.acquire() as connection, connection.transaction():
                await connection.execute(sql("session_role_maintenance"))
                try:
                    yield connection
                finally:
                    await connection.execute(sql("session_role_app"))
        except (OSError, asyncpg.PostgresError) as error:
            raise StorageUnavailableError(str(type(error).__name__)) from error

    async def create_job(self, row: JobRow) -> JobRow:
        """Insert under the tenant; a repeated request hash returns the organisation's row."""
        async with self._storage.tenant(row.organization_id) as connection:
            inserted = await connection.fetchrow(
                sql("job_insert"),
                row.id,
                row.organization_id,
                row.capability,
                row.request_hash,
                row.envelope,
                row.payload,
                row.payload_hash,
                row.state,
                row.job_expires_at,
                row.created_at,
            )
            if inserted is not None:
                return _row_of(inserted)
            existing = await connection.fetchrow(
                sql("job_by_hash"), row.organization_id, row.request_hash
            )
        return _row_of(existing) if existing is not None else row

    async def read_job(self, organization_id: UUID, job_id: UUID) -> JobRow | None:
        """Read under the tenant; the policy hides every other organisation's row."""
        async with self._storage.tenant(organization_id) as connection:
            record = await connection.fetchrow(sql("job_read"), organization_id, job_id)
        return _row_of(record) if record is not None else None

    async def claim_job(self, now: datetime, per_organization: int) -> JobRow | None:
        """Take the oldest queued row under the per-organisation bound; skip what others hold."""
        async with self._maintenance() as connection:
            record = await connection.fetchrow(sql("job_claim"), now, per_organization)
        return _row_of(record) if record is not None else None

    async def finish_job(self, row: JobRow) -> None:
        """Write the final state, the result or the error, and when the result expires."""
        async with self._maintenance() as connection:
            await connection.execute(
                sql("job_finish"),
                row.id,
                row.organization_id,
                row.state,
                row.finished_at,
                row.result_expires_at,
                row.result,
                row.error,
                row.quarantine_reason,
            )

    async def requeue_job(self, organization_id: UUID, job_id: UUID) -> None:
        """Return a running row to the queue."""
        async with self._maintenance() as connection:
            await connection.execute(sql("job_requeue"), job_id, organization_id)

    async def count_jobs(self, state: str, organization_id: UUID | None = None) -> int:
        """How many rows are in the state — one organisation's, or every organisation's."""
        async with self._maintenance() as connection:
            value = await connection.fetchval(sql("job_count"), state, organization_id)
        return int(value or 0)

    async def purge_jobs(self, before: datetime) -> int:
        """Delete final rows whose result expired before the instant, per organisation."""
        async with self._maintenance() as connection:
            rows = await connection.fetch(sql("job_organizations"), before)
            purged = 0
            for record in rows:
                value = await connection.fetchval(
                    sql("job_purge"), record["organization_id"], before
                )
                purged += int(value or 0)
        return purged
