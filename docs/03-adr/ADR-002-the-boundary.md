---
id: ADR-002
title: The boundary — one caller, no product table, no business rule, data classes at the door
status: Accepted
date: 2026-09-18
deciders: AI service lead
supersedes: —
superseded_by: —
level: 3
---

# ADR-002 — The boundary

## Context

The previous system's assisted functions read product tables directly (`ph_issues`, comments,
profiles, releases, test cases), decided product rules inside prompts (what a "story" needs,
which children an epic gets), wrote results back, and sent names and emails to providers. Every
one of those is a coupling the backend cannot see, a tenancy hole the backend cannot close, and
a rule the product cannot change without editing a prompt. The backend's `ARCH-004 §7` classifies
every column; `RESTRICTED` includes names, emails and IPs.

## Options considered

1. **The service reads the product database (read replica, read-only role)** — fewer request
   fields; a second schema copy that drifts; tenancy enforced twice; a business rule inevitably
   moves into the service because the data is there.
2. **The service consumes the backend's events and builds its own read model of product facts**
   — the service becomes a second source of truth for work items; retention and deletion have
   to be mirrored; the backend's ownership rule (`ARCH-012` of that repository) is broken.
3. **The backend sends what a capability needs, classified, in the request; the service keeps
   only what it produces** — this decision.

## Decision

The service is called only by the backend, through the contract, with a service token. It has
no connection to the product database and no copy of its schema. Every request carries
`organization_id` and every field's data class; `RESTRICTED` has no field in the contract and
is refused at the door by the scanner. A rule the capability needs (a type list, allowed
transitions) arrives as data and is validated against, never decided. The service's own
storage holds embeddings, caches, jobs, eval runs and a content-free provider log, per tenant
with RLS. No tenant data trains anything; provider retention is refused in configuration. The
result is a proposal with provenance; the backend decides what it means. The service never
calls the backend (`ADR-007`).

## Invariants

- `INV-001` — every tenant table carries `organization_id NOT NULL`, indexed — `tools/checks/tenancy`
- `INV-002` — every query on a tenant table is scoped by `organization_id` — `tools/checks/tenancy`
- `INV-003` — every tenant table has RLS with the `app.org_id` policy — `test_every_tenant_table_has_rls`
- `INV-004` — the application role cannot bypass RLS — `catalyst-ai check`
- `INV-005` — no module imports a product schema or configures the product database — `test_no_product_schema_import`, `test_no_product_database_config`
- `INV-006` — the service never calls the backend — `test_service_never_calls_backend`
- `INV-007` — every request field declares a data class — `tools/checks/classification`
- `INV-008` — no `RESTRICTED` field exists in the contract; matching values are refused — `tools/checks/classification`, safety tests
- `INV-009` — a cache entry and an index row are scoped by organisation — `tools/checks/tenancy`, contract tests
- `INV-010` — no tenant input trains or fine-tunes; provider retention is off — register rows, `catalyst-ai check`

## Consequences

Requests are larger; the backend assembles context (`ARCH-002 §2`). People are opaque labels
(`Q-001`). A capability that needs a product rule the backend cannot express as data is a
`Q-NNN`, which is the point. Tenancy is enforced once per layer and testable in this repository
alone.

## Revisit triggers

- A capability whose request would exceed the size limit because the backend must send a whole
  corpus — the answer is `knowledge-ingest` with the backend as the sender, not a database read.
- The backend proposes a declared read-model export (a signed, versioned snapshot the backend
  pushes) — an ADR that extends this one; a read by the service stays out.

## Enforcement

`RULE-006` rows for the boundary, classification, tenancy; `tests/architecture/test_boundary.py`.
