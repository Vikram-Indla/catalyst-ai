---
id: ARCH-001
title: System overview — the service in the product's landscape
status: Locked
version: 1.0.0
owner: AI service lead
created: 2026-09-18
---

# ARCH-001 — System overview

## 1. What the service is

One Python process (`catalyst-ai`) in front of one PostgreSQL database of its own, exposing one
OpenAPI contract over HTTP, called by exactly one client: the Go backend. It provides
**capabilities** — improve a story, generate child items, find similar items, summarise a thread,
translate a field, answer over a document set, converse over supplied context — and nothing else.
Every capability takes classified inputs from the request, runs a deterministic pipeline around one
sampled model call, and returns a schema-valid result with provenance.

## 2. Where it sits

```
 web app ─┐                                      ┌─ provider A (first: the previous system's)
 mobile ──┼─▶ Go backend ──(OpenAPI, service token)──▶ catalyst-ai ─┼─ provider B (through the same port)
 integr. ─┘        │                                   │            └─ …
                   │                                   ▼
             product database                  the service's own database
             (never read by catalyst-ai)       (embeddings · caches · eval runs · provider log)
```

- The web app, the mobile app and integrations never call this service; the backend owns the
  trigger, the permission check, the audit event, and what the result means (`ARCH-002 §1`).
- The service never calls the backend (`ADR-007`). Long work is a job the backend polls.
- Providers are reached only through the `Provider` port (`ARCH-005`); the first is the provider
  the previous system's behaviour was tuned on; any other is a register row.
- The service's own database holds embeddings, caches, eval runs and the content-free provider
  log, per tenant with row-level security (`ARCH-006`, `ADR-006`). It holds no product fact.

## 3. Capability families

| Family | Capabilities (planned, `docs/04-ledgers/capabilities.md`) | Shape |
| --- | --- | --- |
| Rewrite | `improve-story`, `improve-comment`, `translate-field` | text in, text out, schema-validated, language-aware |
| Structured generation | `generate-stories`, `generate-epics`, `suggest-children`, `generate-workflow`, `generate-test-cases` | items in, a typed tree out, validated against a supplied type list |
| Summaries | `summarize-comments`, `summarize-standup`, `summarize-chat`, `digest`, `release-notes`, `post-mortem` | items in, a bounded structured summary out |
| Retrieval | `similar-items`, `search-items`, `knowledge-ingest`, `knowledge-ask`, `knowledge-generate` | per-tenant index in the service's database; hybrid search; grounded answers with provenance |
| Assistant | `assistant-chat` | streaming, tool-free, grounded on supplied context only |

## 4. Runtime shape

| Concern | Design |
| --- | --- |
| Process | `uvicorn` running the FastAPI app; one process per replica; horizontally scaled behind the platform ingress |
| Ports | the contract on the API port; `/healthz`, `/readyz`, metrics on the ops port |
| Authentication | a service token from configuration in `Authorization: Bearer`; verified by middleware before any route; no user identity is trusted from the request — the backend has already decided the user may do this |
| Tenancy | `organization_id` on every request; every storage query and every cache key carries it (`ARCH-002 §2`) |
| Short work | synchronous operations with `Idempotency-Key`; per-capability timeout from the budget (`ADR-007`) |
| Long work | `POST …:jobs` returns `202` with a job id; the backend polls `GET /v1/jobs/{id}`; results expire (`ADR-007`) |
| Streaming | server-sent events with typed frames and a terminal frame (`ARCH-004 §4`) |
| Jobs | an in-process worker over the service's own `jobs` table; no broker (`ADR-007 §3`) |
| Configuration | one typed settings object read once at startup; `catalyst-ai check` validates it (`RULE-003 §5`) |

## 5. What the service is not

Not a chat product, not a workflow engine, not a search engine for the product database, not a
place where a business rule lives. If a capability needs to know a rule of the product (which
transitions are legal, who may see an item, what a "story" is in this organisation), the backend
sends the rule as data in the request. A capability that cannot be expressed that way is a
`Q-NNN`, not a query.
