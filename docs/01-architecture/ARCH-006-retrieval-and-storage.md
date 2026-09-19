---
id: ARCH-006
title: Retrieval and the service's own database
status: Locked
version: 1.0.0
owner: AI service lead
created: 2026-09-18
---

# ARCH-006 — Retrieval and the service's own database

## 1. One database, the service's own

PostgreSQL with `pgvector`, owned and migrated by this repository, reachable only by this
service (`ADR-006`). It holds what the service produces and nothing the product owns:

| Table family | Holds | Tenancy | Lifecycle |
| --- | --- | --- | --- |
| `embeddings_<corpus>` | vector, embedding model version, chunk provenance, source key and version supplied by the backend | tenant, RLS | re-embedded on model change; deleted on the backend's `knowledge.forget` call or organisation deletion |
| `cache_entries` | key (`ARCH-008 §3`), response model JSON, expiry | tenant, RLS | TTL; purged by the retention job |
| `jobs` | job id, capability, status, request hash, result JSON, expiry | tenant, RLS | expires after `job_result_ttl` (`ADR-007`) |
| `provider_calls` | organisation, capability, versions, model, tokens, cost, latency, outcome, cache hit — never content | tenant, RLS | retention per `ARCH-010 §3` |
| `eval_runs` | set version, prompt version, model, scores, p95s, git revision | global (synthetic data only) | kept |
| `tenant_budgets` | per-organisation, per-capability spend counters for the window | tenant, RLS | rolling |

Every tenant table: `organization_id UUID NOT NULL`, indexed, RLS enabled with the `app.org_id`
policy, the application role unable to bypass it (`INV-001..004`). Access goes through one
`platform/storage` package (asyncpg, typed query functions, no ORM); SQL outside
`platform/storage/queries/` fails `tools/checks/sql`.

## 2. Chunking is a recorded decision

Each corpus (`work_items`, `pages`, `documents`, `knowledge`) declares in
`retrieval/corpora.py`: chunk size, overlap, structure awareness (headings, tables, slides),
the embedding model alias, and the lexical fields. Changing any of these is a re-embed of the
corpus and an entry in the eval-sets ledger; the retrieval eval (recall@k on a labelled set,
`ARCH-007 §4`) runs before and after.

## 3. Hybrid search, per tenant

Search combines vector similarity and lexical match (`tsvector` on identifiers and exact
phrases) with a documented fusion; results carry a score and provenance. Every query is scoped
by `organization_id` before any similarity operator runs — the index is never shared across
organisations, and identical text in two organisations produces two rows.

## 4. Documents are hostile

Parsing (`docx`, `pptx`, `pdf`, images with OCR) runs in `retrieval/parsers/` under size limits,
time limits, no macros, no external fetches, in a subprocess that can be killed; a parser failure
is `ai.input.rejected` with a reason class, never a crash. Extracted text inherits the document's
data class; images are described, not stored, unless the capability descriptor says otherwise.

## 5. Rebuild

Every index is rebuildable from what the backend can resend: `POST /v1/knowledge-ingest:jobs`
with the same source keys produces the same rows. A runbook names the rebuild; the retrieval
eval proves it converged.
