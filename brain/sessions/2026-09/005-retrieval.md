# 005 — retrieval

**Date:** 2026-09-20 · **Ticket:** AI-005 · **Capability or package:** search, retrieval, platform/storage, providers/gemini (embed), evals · **Author:** a contributor

## Read
`ARCH-006` (the service's own database, chunking as a recorded decision, hybrid search per
tenant, rebuild), `ARCH-007 §4` (retrieval evals), `ADR-006` (own PostgreSQL with `pgvector`,
RLS, `platform/storage` as the only SQL), `ADR-004`, `ADR-005`, `RULE-005`, `RULE-006` (the
storage and tenancy rows). The previous system's `ai-similar-items` (a model ranking 100
candidates of the same project by summary — no index, no embedding), `ai-search-issues` (not a
search: a natural-language-to-filter translator that also sent `current_user` to the provider)
and `_shared/embed_stage.ts` (layout-aware chunking, one batch embedding call, `content_hash`
per chunk, the model id stored with every vector) for behaviour.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-005
Capability:      search v1.0.0 — index.upsert, index.delete, search.run (kind sync; alias embed-default; no prompt)
Inputs:          documents[].title, documents[].text, search text · CONFIDENTIAL; external_id, content_hash,
                 exclude_external_ids[] · INTERNAL; corpus, kind, data_class (never RESTRICTED), mode, kinds[], k · PUBLIC
Tenant boundary: organization_id on every request; two tenant tables (index_documents_work_items,
                 embeddings_work_items) with organization_id NOT NULL, indexed, RLS forced, the app role bound
                 by the app.org_id policy; every query file carries organization_id; the cache untouched (no caching)
Provider/model:  gemini · embed-default → gemini-embedding-001 (768 of 3 072 dimensions, task types, normalised)
Prompt version:  none (prompt_version "0")
Eval set:        evals/search v1 · 146 cases over a 114-line corpus · recall_at_10 0.85, mrr 0.70, isolation,
                 provenance, filters, inertness 1.0, overall 0.90 · runs against a real PostgreSQL
Budget:          p95 latency 2 000 ms · p95 cost 400 µ$ · timeout 10 000 ms · index budget 500 000 chunks/org
Failure mode:    ai.index.document_too_large (413), ai.index.unavailable (503, retry_after), ai.budget.exceeded
                 with detail index_budget; the door's codes; the provider codes on the embedding call
Cache:           none for search results; unchanged content_hash at the current version costs nothing
Safety:          the door's scanner over every text; retrieval never instructs a model (8 injection cases);
                 6 cross-tenant cases with verbatim copies under another organisation; RLS with the layer bypassed
Contract:        index.upsert, index.delete, search.run ADD; GenerateChildrenResponse.index_consulted ADD; not breaking
Invariants:      INV-001..004, INV-007, INV-011, INV-024..026, INV-030, INV-033, INV-039, INV-042, INV-043
Blast radius:    SYSTEM (db/migrations, the port gains model_id and EmbedRequest.purpose) — CONTRACT for the backend
Decision level:  2
ADR:             none new (ADR-006 applied as written)
```

## Changed
- `db/migrations/20260920100000_retrieval_work_items.sql` — the two tenant tables, HNSW and GIN indexes, the two roles, forced RLS, the tenant and maintenance policies
- `platform/storage/{rows,port,memory,postgres,migrate}.py`, `queries/*.sql` — the `Storage` seam; PostgreSQL over `asyncpg` with the `pgvector` codec (`SET ROLE catalyst_ai_app` per connection, `app.org_id` per transaction, the maintenance role only inside `organizations()`); the in-memory store for unit tests; the forward-only migration runner; one statement per query file with table placeholders
- `retrieval/{corpora,chunking,embeddings,lexical,fusion,ingest,search,jobs}.py` — the `work_items` declaration (1 000-char windows, 120 overlap, 768 dimensions, revision 1); paragraph packing with overlap; batched embeddings through the port; the two lexical query forms; reciprocal rank fusion at document level with provenance; upsert with hash and version checks and the index budget; hybrid search that costs nothing on an empty corpus; the re-embed and retention jobs
- `capabilities/search/{descriptor,pipeline,indexing,postprocess,routes}.py` — the three operations; the search pipeline is `parse → validate → retrieve → postprocess`
- `capabilities/generate_children/{retrieve,pipeline,postprocess}.py`, `platform/pipeline/stages.py` — the optional `retrieve` slot in the runner; the tenant's indexed items at the child level join the sibling pool; `index_consulted` on the response
- `providers/gemini/{adapter,errors}.py`, `providers/port.py` — `batchEmbedContents` with task types and dimensions, normalisation, cost from estimated tokens, unreadable bodies mapped; `Provider.model_id`, `EmbedRequest.purpose`
- `contract/{search,errors,generate_children}.py`, `config/settings.py`, `app.py`, `cli.py` — the models; two codes; four settings; the storage lifecycle and `/readyz` storage check; `migrate`, `reembed`, `retention`
- `tools/checks/{pipeline,tenancy,gate,structure}.py`, `tools/rules.py`, `Makefile` — retrieval-only pipelines; placeholders count as tenant tables; `--skip` lists; `budgets-check` after `evals` (`F-006`); `work_items` no longer a product-table prefix (`F-005`); `platform/storage` may import the untyped codec; the file walk never enters a skipped directory (the gate took a minute per check over a bind mount once `.venv` grew); `make ci` disables the container reaper and reaches the database by its bridge address
- `tools/{evalkit,evals,record,authored,evalsets,corpus_terms}.py` — one registry with a per-set setup and database; the retrieval set indexes its corpus first, against a throwaway `pgvector` container or `CATALYST_AI_EVAL_DATABASE_URL`; the authored embedding stand-in; the corpus and set generator
- `evals/search/{corpus.jsonl,set.jsonl,graders.py,thresholds.yaml,README.md}`, `tests/fixtures/providers/gemini/search/` — set v1 and 142 authored fixtures
- `tests/storage/` (a real database through `testcontainers`: the seam's contract, RLS with the application layer bypassed, migration idempotence), `tests/unit/**` (one module per new module; the chunking property test), `tests/contract/test_search.py`
- `docs/`: ledgers (capabilities, errors, config, eval-sets, providers, invariants INV-004, contracts changelog), `THREAT-005-retrieval.md`, runbooks `index-rebuild.md`, `retention.md`, the capability line; `ADR-003` rows for the stubs and the codec; `.env.example` with the keys the lead fills; `pytest.ini` (the container library's warning), `mypy.ini`

## Verify
```
$ make verify
ruff / mypy (233 files + each set's graders) / lint-imports   All checks passed! · Success · Contracts: 5 kept, 0 broken.
tools.checks.gate --skip coverage,budgets                     GATE GREEN (43 checks)
tools.api · oasdiff                                           api\openapi.yaml matches the app · no breaking change against main
pytest tests/architecture · pytest --cov                      24 passed · 346 passed in 53.53s · Total coverage: 99.33%
tools.checks.gate --only coverage                             GATE GREEN (1 checks)
pytest tests/storage (testcontainers pgvector/pgvector:pg17)  3 passed — the seam's contract, RLS with the layer bypassed, migrate idempotent
make evals                                                    -- search v1 - 146 cases (real PostgreSQL in a throwaway container)
                                                              recall_at_10 0.914 (0.85) · mrr 0.787 (0.7) · tenant_isolation 1.000 (1.0)
                                                              provenance_present 1.000 (1.0) · kinds_respected 1.000 (1.0) · injection_inert 1.000 (1.0)
                                                              overall 0.950 (0.9) · p95 latency 40 ms (2000) · p95 cost 14 micro-dollars (400)
                                                              -- generate-children v1 - 139 cases · 1.000 on every grader · p95 20 ms · 1 395 micro-dollars
                                                              -- improve-story v1 - 52 cases · 1.000 on every grader · p95 18 ms · 448 micro-dollars
                                                              EVALS GREEN
tools.checks.gate --only budgets                              GATE GREEN (1 checks)
pip-audit / gitleaks / licences                               No known vulnerabilities found · no leaks found · GATE GREEN
selftest                                                      45/45 checks red on their plant
VERIFY GREEN
```
```
$ make ci     (python:3.12.14-slim, the workflow's steps verbatim; the reaper disabled, the database reached by its bridge address)
All checks passed! · Success: no issues found in 233 source files · Contracts: 5 kept, 0 broken.
GATE GREEN (43 checks) · api/openapi.yaml matches the app · oasdiff: no breaking change against main
24 passed · 346 passed in 119.34s · Total coverage: 99.33% · GATE GREEN (1 checks)
pytest tests/storage: 3 passed (a throwaway pgvector/pgvector:pg17 started from inside the image)
EVALS GREEN (search recall@10 0.914 · mrr 0.787 · improve-story 1.000 · generate-children 1.000) · GATE GREEN (1 checks)
No known vulnerabilities found · no leaks found · GATE GREEN (1 checks)
selftest: 45/45 checks red on their plant
VERIFY GREEN
```

## Eval and budget numbers
search set v1, no prompt, `embed-default`, against a real PostgreSQL in a throwaway container:
**recall@10 0.914 (floor 0.85) · MRR 0.787 (0.70) · tenant_isolation, provenance_present,
kinds_respected, injection_inert 1.000 (1.0) · overall 0.950 (0.90) · p95 latency 40 ms (budget
2 000) · p95 cost 14 µ$ (400)** over 146 cases. Authored fixtures: a hashed bag of stems and
trigrams — the numbers prove the pipeline, the HNSW index under a tenant filter, the fusion,
tenancy and the graders, not the live model; the misses are template-heavy story→bug pairs and
paraphrases. improve-story and generate-children unchanged at 1.000 (generate-children's
retrieve stage makes no call when the organisation has nothing indexed, which is the eval's
state). Planted regression (reverted, red): the vector leg ignoring `exclude_external_ids` — the
item itself ranks first in every `similar` case → `mrr 0.608 < 0.7`, `EVALS RED`.

## Decisions and questions
- D-013..D-019 proposed (one package with three operations; retrieval-only pipelines; the two
  database roles; the eval against a real database; embedding versions; de-duplication over the
  index; `budgets` after `evals`).
- F-005..F-010 found; F-005, F-006, F-007 closed in this session.
- Q-006 (one operation or one concern per package — `ARCH-003 §1`), Q-007 (the backend's `kind`
  vocabulary and indexing events).

## Commit
Two proposals:
1. Files: `src/**`, `db/migrations/**`, `tools/**`, `tests/{unit,contract,storage}/**`, `evals/search/{graders.py,thresholds.yaml,README.md}`, `pyproject.toml`, `mypy.ini`, `pytest.ini`, `Makefile`, `.env.example`, `docs/**`, `brain/**`
   Proposed: `feat(search): retrieval — own database with RLS, hybrid search, versioned embeddings`
2. Files: `uv.lock`, `api/openapi.yaml`, `evals/search/{corpus.jsonl,set.jsonl}`, `tests/fixtures/providers/gemini/search/**`
   Proposed: `gen: lockfile, contract document, corpus and authored fixtures for search v1`
Green light: given by the lead on 2026-09-21 — committed on local `main` in the proposed order (no remote yet)

## Next
The lead's review of `D-013..D-019` and `Q-006`; the live recording of the three sets when the key
arrives (`CATALYST_AI_RECORD_PROVIDER_KEY`); the summaries and translation card.
