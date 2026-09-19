---
id: ADR-007
title: The job model — synchronous operations with idempotency keys for short capabilities; polled jobs for long ones; the service never calls the backend
status: Accepted
date: 2026-09-18
deciders: AI service lead, backend lead (announced; the backend must be able to call it)
supersedes: —
superseded_by: —
level: 3
---

# ADR-007 — The job model

## Context

Capabilities range from a two-second rewrite to a multi-minute document ingest. The backend runs
its own job system on PostgreSQL (river, `ARCH-006` of that repository) with an `ai` queue, and
returns `202 + Location` to its clients for long work. The previous system mixed both: some
functions blocked the HTTP request for a minute, some wrote progress into tables the client
polled. Two things must be true here: the backend can call every capability from a request
handler or from a worker without special cases, and the service never calls the backend
(`ADR-002`) — a callback URL would give the service a backend credential and reverse the
dependency direction.

## Options considered

1. **Everything synchronous** — simple; a 90-second ingest holds a connection, an ingress
   timeout truncates it, and a retry re-runs it.
2. **Everything a job with a callback to the backend** — uniform; the service holds a backend
   URL and a token and calls it (forbidden); a failed callback is a lost result.
3. **Everything a job, polled** — uniform; a two-second rewrite pays a round trip and a table
   write it does not need.
4. **Short capabilities synchronous with idempotency keys; long capabilities a polled job with
   an expiring result; no callbacks** — this decision.

## Decision

A capability whose timeout (`ARCH-008 §1`) is **at most 20 seconds** is a synchronous
operation: `POST /v1/<capability>` with `Idempotency-Key`, the response cached by key and
organisation for the capability's TTL, the adapter's timeout as the deadline. A capability over
that line (ingest, batch embedding, digests over many items, knowledge generation) is a **job**:
`POST /v1/<capability>:jobs` validates the request (stages 1–2 run synchronously, so a rejected
input fails fast), stores a `jobs` row keyed by request hash and organisation, returns `202`
with `Location: /v1/jobs/{id}`; the backend's worker polls `GET /v1/jobs/{id}` (`queued`,
`running`, `succeeded` with the result, `failed` with the error envelope, `expired`) with the
`Retry-After` the response carries; results expire after `job_result_ttl`. Jobs run in the
service's own worker (`catalyst-ai worker`) over the `jobs` table with `SELECT … FOR UPDATE SKIP
LOCKED`, bounded concurrency per organisation, and idempotency by request hash — a second
`POST` with the same hash returns the existing job. The service never calls the backend: no
callback, no webhook, no event. Streaming capabilities are synchronous with SSE
(`ARCH-004 §4`). The 20-second line is a constant in `platform/jobs`; `tools/checks/capabilities`
fails a synchronous capability whose timeout exceeds it.

**What the backend must do:** call synchronous operations with an `Idempotency-Key` it derives
from its own command; for job operations, enqueue a river job that submits, then polls with
`Retry-After` until terminal, then stores the result or the error under its own audit; treat a
missing terminal state after `job_result_ttl` as `ai.job.expired` and resubmit.

## Invariants

- `INV-006` — the service never calls the backend — `test_service_never_calls_backend`
- `INV-027` — a synchronous capability's timeout is ≤ the job line — `tools/checks/capabilities`
- `INV-028` — a job is idempotent by request hash and organisation; a second organisation cannot read it — contract tests
- `INV-029` — every job result expires; the retention job purges it — storage tests

## Consequences

Two shapes, one rule for choosing. The backend's worker is the only place that polls, so the
web app never sees the service. No broker in this service; the `jobs` table is enough at the
concurrency the budgets allow, and the revisit trigger says when it is not.

## Revisit triggers

- Job queue age p95 exceeds 60 seconds at the declared per-organisation concurrency for a week.
- A capability needs progress frames for a long job — an SSE variant of `jobs.get` is a new
  operation under this ADR, not a callback.
- The backend asks for push instead of poll — re-open with the direction-of-calls question first.

## Enforcement

`tools/checks/capabilities`, `test_service_never_calls_backend`, the job contract tests,
`tests/storage/test_jobs.py`.
