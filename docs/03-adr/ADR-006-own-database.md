---
id: ADR-006
title: The service's own PostgreSQL with pgvector — per-tenant rows with RLS; no product data; no separate vector store
status: Accepted
date: 2026-09-18
deciders: AI service lead
supersedes: —
superseded_by: —
level: 3
---

# ADR-006 — The service's own database

## Context

The service produces embeddings, cache entries, job results, eval runs and a provider log, and
needs somewhere to keep them. The previous system kept `ai_*` tables inside the product
database beside `ph_issues` — the service could read product rows by accident and the product
could not delete an organisation without knowing the AI tables. The boundary (`ADR-002`) forbids
the product database. Embeddings need a vector index; the backend's own storage rules (`ADR-004`
of that repository) show that per-tenant rows with RLS are the isolation that survives a bug.

## Options considered

1. **The product database, a schema of its own** — one database to run; the boundary is a
   convention, not a wall; the backend's migrations and this service's collide.
2. **A managed vector database plus a small relational store** — two systems, two tenancy
   models, one of them without RLS; content leaves the platform's perimeter.
3. **One PostgreSQL of the service's own, with `pgvector`, migrated by this repository,
   reachable only by this service** — this decision.

## Decision

`catalyst-ai` owns one PostgreSQL database with the `pgvector` extension. Every tenant table
carries `organization_id UUID NOT NULL`, indexed, with RLS enabled and the `app.org_id` policy
set per session by `platform/storage`; the application role cannot bypass it. Tables:
`embeddings_<corpus>`, `cache_entries`, `jobs`, `provider_calls`, `tenant_budgets` (tenant) and
`eval_runs` (global, synthetic). Access is typed query functions over `asyncpg` in
`platform/storage/queries/`; no ORM, no SQL elsewhere. Migrations are forward-only SQL files
under `db/migrations/`, applied by `catalyst-ai migrate`. The compose file runs the same image
the platform runs. A vector store other than PostgreSQL is a superseding ADR with the numbers
that PostgreSQL could not meet.

## Invariants

- `INV-001..004` — tenancy of every tenant table (`ADR-002`)
- `INV-024` — SQL lives only in `platform/storage/queries/`; no `SELECT *` — `tools/checks/sql`
- `INV-025` — every migration is forward-only with a header; every foreign key is indexed — `tools/checks/migrations`
- `INV-026` — every index is rebuildable from what the backend can resend — the rebuild runbook and the retrieval eval

## Consequences

One stateful system to operate; embeddings, caches and budgets share transactions and tenancy.
Organisation deletion is one call (`RULE-009 §4`). Scale limits of `pgvector` (index size per
organisation, recall at high dimensions) are measured by the retrieval eval before they are a
problem; the revisit trigger says when.

## Revisit triggers

- Retrieval recall@10 on the largest organisation's corpus falls below its floor with an
  HNSW index tuned within the documented ranges.
- p95 retrieval latency exceeds its budget on two consecutive eval runs at production scale.
- The platform team decides on managed PostgreSQL without the `pgvector` extension.
- The platform offers `pgvector` at or above the version the HNSW settings need (0.5.0) — or
  stops offering it: the migrations require the extension and never create it, and the
  development image carries the managed tier's version.

## Enforcement

`tools/checks/tenancy`, `tools/checks/sql`, `tools/checks/migrations`, `test_every_tenant_table_has_rls`,
`tests/storage/`.
