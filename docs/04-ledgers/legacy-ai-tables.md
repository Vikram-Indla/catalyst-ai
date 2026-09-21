# Legacy AI tables — where each of the previous system's `ai_*` tables lands

The previous system kept forty-six `ai_*` tables in the product database (forty-three when the
migrations are read for upper-case `CREATE TABLE` only — the count the card carried; three more
were created in lower case). None is migrated as
it stands: this service holds no product table (`ARCH-002`) and its own schema is the four tables
of `ARCH-006` plus the retrieval pairs. Each row below names the destination of the *state* a
table held — this service (which table or corpus), the backend (which module keeps it, as
announced to the backend), or dropped (why). The count is the migrations' own (a case-insensitive grep for `create table … ai_` → 46);
the "written by" column is what the previous functions or web client
touched, from the same source.

| Table | Held | Written by | Destination | Note |
| --- | --- | --- | --- | --- |
| `ai_documents` | a document record per uploaded file (title, status, class) | `docintel-*` | backend — the `folio` / `wiki` modules own the document record; this service holds only `index_documents_documents` (key, hash, class, versions) | the record is the product's; the index row is the service's |
| `ai_document_versions` | one row per re-upload | `docintel-ingest` | backend | versioning is the product's; the service is idempotent by content hash |
| `ai_document_pages`, `ai_document_blocks`, `ai_document_tables`, `ai_document_images` | the parsed layers of a file: pages, text blocks, tables, page images | `docintel-ingest`, `-analyze`, `-sync` | dropped | the service keeps chunks, not layers; images are not parsed (no OCR in v1, the register says what it would need); tables are text |
| `ai_document_chunks`, `ai_document_embeddings` | chunks and vectors per document | `docintel-ingest`, `-sync`, `-generate` | this service — `index_documents_documents` and `embeddings_documents` under RLS, per organisation and space | the one true home of retrieval state |
| `ai_document_jobs`, `ai_sync_runs` | ingest and sync job rows | `docintel-ingest`, `-sync` | dropped | ingest is synchronous and idempotent (`documents.ingest`); the backend re-ingests on change; no job table |
| `ai_document_links` | links found in documents | web client | dropped | never read by a function; a product concern if wanted (`Q-014`) |
| `ai_document_themes`, `ai_theme_cache`, `ai_digest_cache`, `ai_ageing_triage_cache` | cached digest themes, per-member theme warmups, digest and ageing caches | `ai-digest`, `ai-theme-prewarm`, web client | dropped | the digest is `summarize` mode `digest` on demand, cached in `cache_entries` for its TTL; the nightly warmup was dropped with its function |
| `ai_extraction_issues`, `ai_requirement_facts` | parser issues and "facts" extracted from documents | `docintel-analyze`, `-sync`, `-generate` | dropped | a parse refusal is a reason class on the response, never a row; facts are not extracted — a reply cites passages |
| `ai_artifact_citations`, `ai_generated_artifacts` | drafts generated from documents and their citations | `docintel-generate` | backend — the draft is a product record once the member keeps it | `documents.generate` returns the draft with its sources; the service stores nothing |
| `ai_docintel_audit_events` | who asked what of which document | web client | dropped in this shape | `provider_calls` holds the content-free row per call (`ARCH-010`); product audit is the backend's audit log |
| `ai_agent_prompts` | prompt texts in a table | `_shared` | dropped | prompts are versioned files (`RULE-008`) |
| `ai_agent_runs` | one row per model call with the prompt and the answer | `_shared`, `docintel-*` | this service — `provider_calls` (content-free: tokens, cost, latency, outcome, versions) | content never enters a row |
| `ai_assist_runs`, `ai_assist_drafts`, `ai_assist_artifacts`, `ai_assist_documents`, `ai_assist_links`, `ai_assist_published_epics`, `ai_assist_approvals`, `ai_assist_exemptions`, `ai_assist_audit_events` | a first-generation "assist" workflow: runs, drafts, artefacts, the documents behind them, the epics it published, approvals and exemptions, its audit | web client (four tables), nothing else | dropped — the feature was superseded by `docintel-*` in the same system (created 2026-01-07, unread by any function) | a product decision to revive an approval flow would be a backend feature (`Q-014`) |
| `ai_briefs` | executive briefs from `alignment-story` | web client | dropped with `alignment-story` (`Q-012`) | |
| `ai_contracts`, `ai_policies`, `ai_route_scopes`, `ai_table_allowlist`, `ai_semantic_dictionary`, `ai_governance_audit_log` | a governance layer: which tables the AI may read, per-route scopes, a dictionary, policies, its audit | web client (governance log), nothing else | dropped | this service reads no product table at all (`ARCH-002`), so an allowlist of tables has nothing to allow; per-organisation budgets and the kill switches are the governance that exists |
| `ai_integration_settings` | provider keys and settings per organisation | nothing (unused) | dropped | one key, the service's, in the environment (`RULE-006`); per-organisation providers are not a v1 feature |
| `ai_feedback`, `ai_summary_feedback` | thumbs up/down on answers and summaries | web client | backend — a `feedback` concern of the product; the service may read it later as eval material (`kb-feedback` in the functions ledger) | never written here |
| `ai_generated_work_items` | items created from generated stories and epics | web client | backend — the `workitems` module creates items; `generate-children` proposes them | the row is the product's |
| `ai_promotion_recoveries` | recoveries of a promotion flow | web client | dropped | tied to the assist workflow above |
| `ai_usage_log` | one row per model call: tokens, cost, the caller | `ai-improve-comment` and the `_shared` gateways | this service — `provider_calls` | content-free, per organisation, with the versions |
| `ai_theme_prewarm_config`, `ai_theme_quota` | the nightly warmup's secret and its per-member quota | the cron | dropped | dropped with `ai-theme-prewarm` (`F-022`) |

Totals: this service 4 (`ai_document_chunks` and `ai_document_embeddings` → the retrieval pair under
RLS; `ai_agent_runs` and `ai_usage_log` → `provider_calls`) · backend 7 (`ai_documents`,
`ai_document_versions`, `ai_artifact_citations`, `ai_generated_artifacts`, `ai_feedback`,
`ai_summary_feedback`, `ai_generated_work_items`) · dropped 35. Forty-six in all.

Beside them the previous system kept twenty-seven `kb_*` tables (the wiki's own records — documents,
spaces, versions, labels, comments, links, restrictions, databases — and `kb_embeddings`,
`kb_cache`, `kb_query_log`, `kb_eval_set`, `kb_eval_results`, `kb_training_questions`) and two
`tm_ai_*` tables (`tm_ai_embeddings`, `tm_ai_usage_log`). The wiki records are the backend's
`wiki` module's by construction (announced with `documents`); `kb_embeddings` and
`tm_ai_embeddings` are the documents corpus of the retrieval index here; the caches, logs, the
training questions and the eval rows are dropped — evaluation lives in `evals/` as versioned
sets, never in a product table.

The backend acknowledges its seven in its own outbox; the two ledgers cite each other by page
name only.
