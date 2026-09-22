# 016 — the job model, built as decided and born verified

**Date:** 2026-09-25 · **Ticket:** AI-016 · **Capability or package:** platform/jobs (new), platform/storage (the jobs table behind a second seam), capabilities/documents (the job path), the contract (two operations, one code, three variables), the CLI worker · **Author:** a contributor

## Read
`ADR-007`'s decision text (the spec: `POST /v1/<capability>:jobs` → `202 + Location`, a `jobs`
table keyed by request hash and organisation, `GET /v1/jobs/{id}` with `Retry-After`, expiring
results, a worker over `SELECT … FOR UPDATE SKIP LOCKED` with bounded concurrency per
organisation, no callbacks), `ARCH-008 §1` (ingest: 30 s per document, 120 s window),
`ARCH-009 §1` (the job row's rule from the previous record), `platform/auth/jobs.py`
(`verify_stored`, `quarantined` — the function this card gives its loop), the storage adapter's
tenant and maintenance sessions and the migrations' policy shape, the documents ingest path
(`payload_of`, the 200 000-character text bound and the 14 MB base64 bound), the `tenancy`,
`interfaces`, `routes`, `journeys` and `tests` checks (each shaped a decision below), the
backend's report on how it polls (a river job that submits, then polls with `Retry-After`).

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-016
Capability or package: platform/jobs — worker, submit/read, the jobs router; platform/storage — JobRow, JobStore (memory, PostgreSQL),
                 nine query files, the jobs migration; capabilities/documents — jobs.py (the size line, submission, the runner);
                 contract/jobs; config — three variables; the CLI worker with drain; app — the runner registry, the jobs router, /readyz
Inputs:          the same IngestRequest as a job; GET /v1/jobs/{id}?organization_id=…
Tenant boundary: the jobs table is a tenant table under RLS (reads by the tenant session); the worker claims under the maintenance role
                 and every maintenance statement is scoped by organisation as well; a poll answers 404 for any other organisation's row
Provider/model:  unchanged (the worker runs the same ingest pipeline)
Prompt version:  unchanged
Eval set:        unchanged (documents-ingest 19 cases: the pipeline is the same, the job path is a transport)
Budget:          unchanged; JOB_TIMEOUT_SECONDS is the worker's deadline
Failure mode:    a row trusted for being in the table → verified again before running, quarantined otherwise; a queued row past its
                 window → expired, never run; a runner past its deadline → failed with ai.provider.timeout; a worker killed mid-job →
                 the row stays running until an operator requeues it (the backlog runbook); a drain → finished or requeued
Cache:           unchanged
Safety:          the payload is never parsed before the proof clears; the hash is computed from the bytes about to run
Contract:        ADD documents.ingest_job, jobs.get, ai.job.not_found, three variables; CHANGE narrowing — documents.ingest refuses above 256 KiB
Invariants:      INV-028, INV-029 (now enforced by tests), INV-055, INV-056 (new)
Blast radius:    SYSTEM — a migration, a worker process, a new seam, the settings, the contract
Decision level:  3
ADR:             ADR-007 → Implemented (D-037); ARCH-012 §3 names the new seam (1.0.1)
```

## Changed
- `db/migrations/20260925100000_jobs.sql` — the `jobs` table: the envelope verbatim, the payload bytes and their hash, the state (a check constraint over the six), attempts, `job_expires_at`, the times, the result and the error as JSON text, the quarantine reason; unique `(organization_id, request_hash)`; indexes for the claim, the purge and the tenant; RLS forced; the tenant and maintenance policies; grants
- `platform/storage/jobrows.py`, `port.py` (`JobStore`, a second seam — memory and PostgreSQL), `jobs_memory.py` (with `plant`, the attacker's tool for the suite), `jobs_postgres.py` (over the storage adapter's pool: tenant reads, maintenance claims with `FOR UPDATE SKIP LOCKED` and the per-organisation count in one statement); the adapter gains a public `pool` and `tenant`
- `platform/jobs/worker.py` — claim → `verify_stored` against **the hash of the payload bytes about to run** → run under `JOB_TIMEOUT_SECONDS` → `succeeded | failed | expired | quarantined`; a catalog error, a timeout and a runner defect each become the row's error (never the exception's text); `serve(stop)` with the total bound, `drain()` finishes inside `SHUTDOWN_DRAIN_SECONDS` and requeues the rest; `draining` for `/readyz`
- `platform/jobs/submit.py` — the row born from the verified request path only (`job_exp` required in the envelope; missing → `401` with `no_job_window` in the security log), the request hash = the envelope's `bh`; `status_of` (a final state carries its result or error; `expired` and `quarantined` say nothing more); `read` → `404 ai.job.not_found` for any other organisation's row or an unknown id
- `platform/jobs/routes.py` — `GET /v1/jobs/{job_id}?organization_id=…` (`jobs.get`, `x-capability: jobs`); the door binds a body-less request's organisation from its query string (`organization_of(body, query)`), the tooling's signer follows
- `capabilities/documents/jobs.py` — the size line (256 KiB of decoded bytes: below it the synchronous path; above it `413` with `use_the_job_operation`), `submit_ingest` (the door synchronously, then the row), `run_ingest_payload` (the stored bytes are the request model or the row fails); `routes.py` — `POST /v1/documents/ingest:jobs` (`documents.ingest_job`, `202`)
- `contract/jobs.py` — `JobState`, `FINAL_STATES`, `JobAccepted`, `JobStatus`; `contract/errors.py` — `ai.job.not_found` (404); the document renderer keeps any `2xx` success response and the example rule checks any `2xx` (F-029)
- `config/settings.py` — `JOB_TIMEOUT_SECONDS` (600, ≤ 3 600), `WORKER_CONCURRENCY` (4, ≤ 64), `WORKER_CONCURRENCY_PER_ORGANIZATION` (2, ≤ 64); `platform/runtime` — `jobs: JobStore` (memory by default; PostgreSQL in the production runtime)
- `app.py` — `job_runners()` at the composition root (platform imports no capability), the jobs router, `/readyz` reports the worker's drain; `cli.py` — `catalyst-ai worker` (the ops app on `OPS_ADDR`, SIGTERM/SIGINT → drain), `retention` purges expired job results
- `tools/rules.py` — `JobStore` in the seams list; `tools/checks/openapi.py` — the example rule over any `2xx`
- tests: `tests/contract/test_jobs.py` (submit → 202 + Location; poll with Retry-After; the result whole; idempotent resubmission; `jobs.get` for the organisation only and 404 otherwise; no `job_exp` → 401; the size line; an expired job; **six attacker rows planted in the store and quarantined on the running loop while the legitimate row succeeded**), `tests/unit/platform/jobs/test_{worker,submit,routes}.py` (result and expiry, a catalog error and a defect, the deadline and an unknown capability, the per-organisation bound, drain finishes-or-requeues, idle serve), `tests/unit/platform/storage/test_{jobrows,jobs_memory,jobs_postgres}.py`, `tests/unit/capabilities/documents/test_jobs.py`, `tests/unit/contract/test_jobs.py`, and `tests/storage/test_jobs.py` against PostgreSQL: idempotency and the policy, three concurrent claims take two rows under the bound, and **six rows raw-inserted into the table while `catalyst-ai worker`'s loop runs — five quarantined, one expired, none executed, the legitimate row succeeded, the counter at five**
- docs: the changelog `ADD` with the "backend must" lines (`job_exp`, `cap: jobs` on polls, the final states), the config and errors ledgers, INV-028/029 wording and INV-055/056, `ADR-007` Implemented with its implementation paragraph, `ARCH-012 §3` (the seam), `THREAT-001` row 2 on the real loop and two residual-risk lines, `docs/06-runbooks/job-quarantine.md` (renamed from `quarantine.md`, as the runbook index names it) and `job-backlog.md` (new), the capabilities ledger's documents row; brain D-037, F-028, F-029, the status

## Verify
```
$ make verify
GATE GREEN (46 checks) · oasdiff: no breaking change against main · 790 passed in 185 s · coverage 99 % · storage suite green against PostgreSQL (the real loop) · fourteen sets EVALS GREEN · pip-audit: no known vulnerabilities · selftest: 48/48 checks red on their plant
VERIFY GREEN
(the first run was red at one fitness test — a method named with a product noun; renamed, second run green)
```
```
$ make ci
GATE GREEN (46 checks) · 790 passed · coverage 99 % · storage green · EVALS GREEN · selftest: 48/48
VERIFY GREEN
stamp: tree 86794516e69a in python:3.12.14-slim at 2026-09-22T11:01:26+00:00 -- green
(this block was written after the stamp; the push's own run re-proves the tree)
```
The real-loop tests, by name: `test_the_attackers_rows_inserted_into_the_database_are_quarantined_on_the_real_loop` (PostgreSQL; rows: no envelope, a made-up one, another organisation's, an edited payload, a forged key under a known id, a closed window), `test_the_attackers_rows_are_quarantined_on_the_running_loop` (the store in memory; the same six shapes plus another capability's), `test_concurrent_claims_take_different_rows_under_the_bound`, `test_drain_finishes_inside_the_window_or_requeues`.

## Eval and budget numbers
No prompt or pipeline moved; the `documents-ingest` set (19 cases, the parse matrix) and the `documents` sets re-run unchanged in `make verify`; no budget line moves. The job path is a transport around the same ingest.

## Decisions and questions
- D-037 (the job model as ADR-007 decided; the payload hashed at execution; the organisation as a query parameter on the poll; the 256 KiB line).
- F-028: the first cut compared the envelope's `bh` to the row's `payload_hash` column — the attacker's test caught it before anything else; the worker hashes the bytes it is about to run. F-029: the document renderer and the example rule assumed `200`.
- The size line, justified: text documents are bounded at 200 000 characters by the contract and never cross it; bytes documents (base64, up to 14 MB) do. 256 KiB of decoded bytes is roughly 250 embedding windows — a few batches, seconds — comfortably inside the 20-second synchronous line of `ARCH-008 §1`; a 14 MB file is thousands of windows and is what the job path is for.
- Stated plainly: (1) the per-organisation bound is honoured by the claim statement, not by a scheduler — a flood from one organisation waits its turn behind the bound, it is not throttled at submission; (2) a worker killed mid-job leaves its row `running` until an operator requeues it (the backlog runbook says how) — a heartbeat is a later line when a second worker exists; (3) `ARCH-012 §3` gained a word (the new seam) — a law page beyond the card's allowance, said here; (4) metrics: `job_quarantined{reason}` on the counters and `jobs_queued`/`jobs_running` through `count_jobs` — the endpoint that renders them is the operational-readiness ticket's.

## Commit
1. Files: `src/**`, `tools/**`, `tests/**`, `db/migrations/20260925100000_jobs.sql`, `docs/**`, `brain/**`
   Proposed: `feat(jobs): the jobs table and a worker that verifies every row before it runs`
2. Files: `api/openapi.yaml`
   Proposed: `gen: contract document with the job operations`
Green light: given

## Next
The backend's poller against the changelog entry; AI-014 (the metrics endpoint, the alerts, the load test on the streaming path, the API's drain).
