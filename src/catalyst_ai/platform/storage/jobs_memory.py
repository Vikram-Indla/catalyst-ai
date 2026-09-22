"""The in-process job store: the same seam as PostgreSQL, for the suite and the single process."""

from dataclasses import replace
from datetime import datetime
from uuid import UUID

from catalyst_ai.platform.storage.jobrows import FINAL, QUEUED, RUNNING, JobRow


class MemoryJobStore:
    """Rows in a dict; claiming is oldest-first under the per-organisation bound."""

    def __init__(self) -> None:
        """Start empty."""
        self._rows: dict[UUID, JobRow] = {}

    async def create_job(self, row: JobRow) -> JobRow:
        """Insert the row, or return the one the organisation already has for the request hash."""
        for existing in self._rows.values():
            if (
                existing.organization_id == row.organization_id
                and existing.request_hash == row.request_hash
            ):
                return existing
        self._rows[row.id] = row
        return row

    async def read_job(self, organization_id: UUID, job_id: UUID) -> JobRow | None:
        """Return the organisation's row, or None for any other organisation's or an unknown id."""
        row = self._rows.get(job_id)
        return row if row is not None and row.organization_id == organization_id else None

    async def claim_job(self, now: datetime, per_organization: int) -> JobRow | None:
        """Take the oldest queued row under the per-organisation bound; mark it running."""
        running = [r.organization_id for r in self._rows.values() if r.state == RUNNING]
        queued = sorted(
            (r for r in self._rows.values() if r.state == QUEUED),
            key=lambda r: (r.created_at, r.id.int),
        )
        for row in queued:
            if running.count(row.organization_id) < per_organization:
                claimed = replace(row, state=RUNNING, started_at=now, attempts=row.attempts + 1)
                self._rows[row.id] = claimed
                return claimed
        return None

    async def finish_job(self, row: JobRow) -> None:
        """Store the row in its final state."""
        self._rows[row.id] = row

    async def requeue_job(self, organization_id: UUID, job_id: UUID) -> None:
        """Return a running row to the queue (a drain that could not finish it)."""
        row = self._rows.get(job_id)
        if row is not None and row.organization_id == organization_id and row.state == RUNNING:
            self._rows[job_id] = replace(row, state=QUEUED, started_at=None)

    async def count_jobs(self, state: str, organization_id: UUID | None = None) -> int:
        """How many rows are in the state — one organisation's, or every organisation's."""
        return sum(
            1
            for r in self._rows.values()
            if r.state == state and organization_id in (None, r.organization_id)
        )

    async def purge_jobs(self, before: datetime) -> int:
        """Delete final rows whose result expired before the instant; return how many."""
        due = [
            r.id
            for r in self._rows.values()
            if r.state in FINAL and r.result_expires_at is not None and r.result_expires_at < before
        ]
        for job_id in due:
            del self._rows[job_id]
        return len(due)

    def plant(self, row: JobRow) -> None:
        """Insert a row the way an attacker with the database would: no API, no verification."""
        self._rows[row.id] = row
