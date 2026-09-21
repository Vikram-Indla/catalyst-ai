---
id: THREAT-005
family: retrieval and knowledge (search; later knowledge-ingest, knowledge-ask)
status: Draft
reviewed: —
asvs: 5.0
llm-top10: 2025
---

# THREAT-005 — retrieval

## Assets

Every indexed document and chunk (`CONFIDENTIAL`, per tenant, at rest in the service's own
database); the vectors (derived from `CONFIDENTIAL` text, same class); the organisation's index
size and versions (`INTERNAL`); the database roles and the provider key (`RESTRICTED`).

## Entry points and trust boundaries

`POST /v1/index/upsert`, `POST /v1/index/delete`, `POST /v1/search`, and the retrieve stage of
`generate-children`. Trust changes at the service token; the request models (`extra="forbid"`,
≤ 100 documents, ≤ 20 000 characters, a `kind` pattern, a hash pattern, no `RESTRICTED` class);
the door (switch, version, scanner over every text, tenant cap); the index budget; the pool's
`SET ROLE catalyst_ai_app` and the per-transaction `app.org_id`; the RLS policies with
`FORCE`; the maintenance role assumed only inside the jobs.

## Attackers

A member through the backend (an instruction in an item, a query shaped as an instruction) · the
backend with a bug (a wrong `organization_id`, a missing filter, a re-sent index of another
tenant) · a tenant script (many documents, many upserts, a giant text) · someone with the
application role's credentials but not the token (the RLS case) · the provider (wrong-size or
missing vectors).

## Threats

| # | Attacker | Entry point | Attack | Mitigation (code) | Verified by | ASVS / LLM |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | backend bug | any | a query or an upsert under the wrong organisation | every query file carries `organization_id`; RLS forced with the tenant policy; the cache key carries the organisation; `tools/checks/tenancy` | `test_rls_holds_with_the_application_layer_bypassed`; eval `tenancy-*`; contract test with two organisations | V4.2 |
| 2 | credential holder | the database | a raw query with no `WHERE` | `SET ROLE catalyst_ai_app` on every pooled connection; the policy reads `app.org_id` and refuses writes for another organisation; no org set → no rows | the storage suite's raw-connection case | V4.2 |
| 3 | member | a document or a query | an instruction in the text | retrieval never instructs a model: the text is embedded and matched, the response is a hit list; the scanner refuses secret shapes; snippets are the tenant's own text | eval `injection-*` (`injection_inert` floor 1.0) | LLM01 |
| 4 | tenant script | `index.upsert` | index growth, cost runaway | ≤ 100 documents per call, ≤ 20 000 characters each (`ai.index.document_too_large`), the total-size door, the per-organisation chunk budget (`ai.budget.exceeded`, `index_budget`) checked before any embedding, the tenant spend cap, unchanged hashes cost nothing | `test_upsert_refuses_over_the_index_budget_before_embedding`; contract tests | LLM10 |
| 5 | provider | the embedding response | wrong-size or missing vectors | the adapter refuses an unreadable body (`ai.provider.unavailable`) and normalises vectors; a stored row always carries model and version | adapter tests | LLM05 |
| 6 | backend bug | `search.run` | mixed embedding versions ranked together after a model change | the vector leg filters on exactly the current model and version; the re-embed job brings rows forward; searches show fewer rows, never wrong ones | `test_filters_kinds_excludes_and_versions`; the index-rebuild runbook | — |
| 7 | member | `search.run` | another tenant's verbatim document surfaces because identical text hashes alike | rows are per organisation; identical text in two organisations is two rows; the search is scoped before any similarity operator runs | eval `tenancy-*`; `test_search_never_crosses_the_organisation` | V4.2 |
| 8 | anyone | logs | document text in a log line | the row model has no content field; `tools/checks/logs` | `test_row_has_no_content_field`; the gate | LLM02 |
| 9 | operator | the jobs | the maintenance role leaks into request handling | assumed only inside `organizations()` and reset in a `finally`; no route reaches it | `test_organizations_and_stale_documents`; code review | V4 |

## Residual risk

- The compose file's login user is a superuser and bypasses RLS; production must use a
  non-superuser login (the retention runbook says so). A check at startup that refuses a
  superuser login is a follow-up.
- Retrieval quality on live embeddings is unmeasured until a key exists; the authored vectors
  reward shared words only.
- Accepted by: pending the lead (`D-NNN`).
