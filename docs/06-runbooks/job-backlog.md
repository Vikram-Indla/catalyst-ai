# Job backlog — queue age, stuck jobs, expiry, the concurrency dials, drain

The worker (`catalyst-ai worker`) claims the oldest queued row whose organisation runs fewer
than `WORKER_CONCURRENCY_PER_ORGANIZATION` jobs, at most `WORKER_CONCURRENCY` at once per process,
with `SELECT … FOR UPDATE SKIP LOCKED` — several processes share one queue without a broker.

## What to look at first

1. `SELECT state, count(*) FROM jobs GROUP BY state` under the maintenance role — the shape of
   the backlog. `queued` growing while `running` sits at the bound means more workers or a wider
   dial; `running` stuck at the same ids means a hung job (below).
2. `SELECT organization_id, count(*) FROM jobs WHERE state = 'queued' GROUP BY 1 ORDER BY 2 DESC`
   — one organisation flooding the queue is what the per-organisation bound is for; the others
   still get their turn.
3. The worker's `/readyz` on the ops port: `worker: false` means it is draining and takes no new
   rows.

## Stuck jobs

A row is `running` for longer than `JOB_TIMEOUT_SECONDS`: the worker enforces that deadline in
process and marks the row `failed` with `ai.provider.timeout`; a row that stays `running` past it
belongs to a worker that died. Restart the worker; a row in `running` with no worker holding it
is returned to `queued` by hand (`UPDATE jobs SET state = 'queued', started_at = NULL WHERE id =
…` under the maintenance role) — its attempts count is kept, so a row that dies repeatedly shows
it.

## Expiry

A queued row past its `job_exp` (the window the backend signed) is marked `expired` by the
worker when it reaches it and never runs; the backend resubmits with a fresh window. A long
backlog therefore shows as a rise in `expired` before anything else: widen the dials or add
workers, and tell the backend its window is shorter than the queue.

## The dials

- `WORKER_CONCURRENCY` (4): raise until the provider's per-organisation concurrency
  (`TENANT_CONCURRENCY_MAX`) or the database pool (`DATABASE_POOL_MAX`) is the limit.
- `WORKER_CONCURRENCY_PER_ORGANIZATION` (2): the fairness dial; raise only when one organisation
  legitimately owns most of the queue.
- `JOB_TIMEOUT_SECONDS` (600): the deadline; `ARCH-008 §1` gives 120 s per document for ingest.
- `JOB_RESULT_TTL_SECONDS` (86 400): how long a result waits for its poll; the retention command
  (`catalyst-ai retention`) purges past it.

## Drain

`SIGTERM` stops claiming; the running rows get `SHUTDOWN_DRAIN_SECONDS` to finish; what is still
running after that is cancelled and returned to `queued` with its attempts count intact, and
`/readyz` reports `worker: false` throughout. A deploy that waits for `/readyz` to turn false
before it kills the process loses no job.
