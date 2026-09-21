# Contracts changelog

Every change to anything the backend relies on (`RULE-003`): an operation, a request or response
shape, an error code, a header, a stream frame, a job status, a configuration variable, a port
method. Newest first. Written by hand in the same change as the contract; `tools/checks/changelog`
fails a change to `api/openapi.yaml` without an entry here.

Entry template:

```
## YYYY-MM-DD · AI-NNN · <capability or platform>
**Kind:** ADD | CHANGE | DEPRECATE | REMOVE | FIX
**What:** <operationId(s) / error code(s) / header(s) / setting(s)>
**Backend must:** <action or "nothing">
**Sunset:** <date, for DEPRECATE>
```

---


## 2026-09-21 · AI-006 · summarize, translate
**Kind:** ADD
**What:** `summarize.run` (`POST /v1/summarize`, `SummarizeRequest {mode: comments | thread, items[] {id, participant, at, text}, item_title?, item_type?, status_changes[] {participant, from_status?, to_status, at}, target_words, language?}` → `SummarizeResponse {summary, empty_reason?, covered_range {first_id, last_id, count}, participants_mentioned[], confidence}`); `translate.run` (`POST /v1/translate`, `TranslateRequest {mode: field | title, text, context?, source_language?, target_language?}` → `TranslateResponse {translated_text, detected_language, target_language, structure_preserved, confidence}`); `ai.input.rejected` gains the detail `target_language_required`; `ai.output.unsafe` gains the detail `participant_not_in_thread`; settings `CAPABILITY_SUMMARIZE__*`, `CAPABILITY_TRANSLATE__*`.
**Backend must:** send people only as participant tokens of the shape `p1`…`p9999`, one token per person per thread, and keep the token-to-person map on its side — the response's `participants_mentioned` and the tokens inside `summary` are what it substitutes back before rendering; never send a name, a handle or an email as a token or inside `item_title` (the pattern refuses tokens, the door refuses emails); send items oldest first with its own ids and read `covered_range` to know what the summary rests on; treat `empty_reason` as a valid outcome; send recorded status moves in `status_changes[]` rather than in comment text when it has them; always send `target_language` for a translation (a missing one is `ai.input.rejected` with `target_language_required`) and read `structure_preserved` before replacing a Markdown field; apply the same `Idempotency-Key`, `capability_version` and `RESTRICTED` rules as for `improve_story.run`.

## 2026-09-20 · AI-005 · search (retrieval)
**Kind:** ADD
**What:** `index.upsert` (`POST /v1/index/upsert`, `IndexUpsertRequest {corpus, documents[] {external_id, kind, title?, text, data_class, content_hash}}` → `IndexUpsertResponse {results[] {external_id, chunks, embedding_model, embedding_version, unchanged}, index_chunks}`), `index.delete` (`POST /v1/index/delete`, `IndexDeleteRequest {corpus, external_ids[]}` → `IndexDeleteResponse {deleted_chunks}`), `search.run` (`POST /v1/search`, `SearchRequest {corpus, mode: similar | query, text, kinds[], exclude_external_ids[], k}` → `SearchResponse {hits[] {external_id, kind, title, score, snippet, provenance}, fusion, embedding_version}`); error codes `ai.index.document_too_large` (413) and `ai.index.unavailable` (503, `retry_after`); `ai.budget.exceeded` gains the detail `index_budget`; `GenerateChildrenResponse` gains `index_consulted: bool` (additive); settings `CAPABILITY_SEARCH__*`, `DATABASE_POOL_MAX`, `RETRIEVAL_INDEX_MAX_CHUNKS_PER_ORGANIZATION`, `RETRIEVAL_DOCUMENT_TTL_DAYS`; port method `Provider.model_id`, `EmbedRequest.purpose`.
**Backend must:** index work items through `index.upsert` from its own events (created, updated, restored — at most 100 per call, `text` under 20 000 characters, `content_hash` = sha256 of the title and text it sent so an unchanged item costs nothing), call `index.delete` on archive, deletion and organisation offboarding, and re-send everything on a rebuild (every index is rebuildable from what the backend can resend); send `kind` in lower snake case (the item level or type — the same vocabulary it filters by); never send a RESTRICTED value in `title` or `text`; treat `hits[]` as ranked candidates and own what a hit means (linking, suggesting, showing); pass `exclude_external_ids` for the item itself and what is already linked in `similar` mode; expect an empty `hits[]` with zero cost while an organisation has nothing indexed; treat `ai.index.unavailable` like `ai.provider.unavailable` (retry after `retry_after_ms`); read `embedding_version` and expect it to change only with a `catalyst-ai reembed` announced here; `generate-children`: read `index_consulted` to know whether the tenant's index took part in de-duplication.

## 2026-09-18 · AI-003 · improve-story
**Kind:** ADD
**What:** `improve_story.run` (`POST /v1/improve-story`), request `ImproveStoryRequest` (every field
classified; `mode`, `item_type`, `title`, `description`, optional `acceptance_criteria`,
`focus_hint`, `parent_title`, `parent_description`, `language`), response `ImproveStoryResponse`
(the envelope plus `improved_description`, `acceptance_criteria`, `rationale`, `changed`,
`confidence`); error codes `ai.contract.version_mismatch`, `ai.capability.disabled`,
`ai.input.rejected`, `ai.input.too_large`, `ai.budget.exceeded`, `ai.provider.unavailable`,
`ai.provider.timeout`, `ai.provider.rejected`, `ai.provider.quota`, `ai.output.invalid`,
`ai.output.unsafe`; header `Idempotency-Key` honoured; settings `PROVIDER_GEMINI_API_KEY`,
`PROVIDER_GEMINI_BASE_URL`, `MODEL_TEXT_DEFAULT`, `CAPABILITY_IMPROVE_STORY__*`.
**Backend must:** send `organization_id` and `capability_version: "1.0.0"` in every body; send no
`RESTRICTED` value (names, emails, IPs, secrets) in any text field — the door refuses with
`ai.input.rejected` and a reason class; send `Idempotency-Key` derived from its own command id on
retries; read `capability_version`, `prompt_version` and `model` from the response and store
them with the proposal; treat `ai.capability.disabled` and `ai.budget.exceeded` as
first-class outcomes (no retry on the first; `Retry-After` on the second); never show the
`rationale` as a stored fact — it is the proposal's explanation.

## 2026-09-18 · AI-004 · generate-children
**Kind:** ADD
**What:** `generate_children.run` (`POST /v1/generate-children`), request `GenerateChildrenRequest`
(every field classified; `target` — `stories` | `epics` | `children`; `hierarchy[]` the organisation's
ordered levels top first; `parent_level`; optional `child_level` — must be the level under the parent;
`parent_title`, `parent_description`, `source_texts[]`, `siblings[] {key?, title}`, `focus_hint?`,
`max_items` 1–20, `language?`), response `GenerateChildrenResponse` (the envelope plus `candidates[]
{type, title, description, acceptance_criteria[], confidence, duplicate_of?}`, `empty_reason?`,
`confidence?`); error codes as `improve_story.run`, with `ai.output.invalid` carrying the detail
`hierarchy_violation` when a candidate is not at the child level and `ai.input.rejected` carrying it
when the request names a child level that is not the parent's next; settings
`CAPABILITY_GENERATE_CHILDREN__*`.
**Backend must:** send the organisation's hierarchy as data on every call (the service knows no
registry) and validate every candidate's `type` against the organisation's enabled types again before
creating anything — the service knows the list it was sent, not the tenant's enablement; treat
`candidates[]` as proposals and own creation, ordering and ranking; skip or merge candidates whose
`duplicate_of` names a sibling; show `empty_reason` when the list is empty rather than retrying;
send extracted attachment text in `source_texts[]` when the product wants attachments considered
(never URLs); apply the same `Idempotency-Key`, `capability_version` and `RESTRICTED` rules as for
`improve_story.run`.
