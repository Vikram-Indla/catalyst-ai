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

## 2026-09-22 · AI-009 · documents
**Kind:** ADD
**What:** `documents.ingest` (`POST /v1/documents/ingest`, `IngestRequest {space_id, document_id, kind, format: docx | pptx | pdf | markdown | text, filename?, title?, content_base64? | text?, data_class, content_hash}` → `IngestResponse {document_id, state: indexed | unchanged, chunks, headings[], embedding_model, embedding_version, index_chunks}`); `documents.ask` (`POST /v1/documents/ask`, `AskRequest {space_id, question, kinds[], k, language?}` → `AskResponse {answer, citations[] {chunk_id, document_id, position, heading_path[], quote}, not_found, confidence}`); `documents.generate` (`POST /v1/documents/generate`, `DraftRequest {brief, sources[] {id, title?, text}, target_words, language?}` → `DraftResponse {title, sections[] {heading, text, sources[]}, empty_reason?, confidence}`); `ai.input.rejected` gains the details `document_too_large`, `document_unsupported`, `document_malformed`, `document_timeout`, `document_restricted`; `ai.output.invalid` gains the detail `uncited_claim`; the storage `Corpus` gains `documents` (the search operations stay on `work_items`: `SearchCorpus`); settings `CAPABILITY_DOCUMENTS__*`; migration `20260922100000_retrieval_documents.sql` (the same shape, roles and policies as `work_items`).
**Backend must:** own the document records, the spaces and who may ask — the service enforces no permission: it reads the space it is told and answers whoever asked; send bytes as base64 with the declared `format` and the sha256 `content_hash` (an unchanged hash costs nothing), or already-extracted text for markdown and plain text; keep the original bytes on its side (the service retains nothing but the extracted chunks); treat every `document_*` detail as a user-visible reason class and never retry a `document_malformed`; expect `not_found` as a normal answer and show it as such; render `[n]` markers against `citations[]` and resolve `document_id` back to its record; treat a draft as a proposal; apply the same `Idempotency-Key` (ask and generate), `capability_version` and `RESTRICTED` rules as everywhere — a document whose extracted text carries a RESTRICTED pattern is refused whole (`document_restricted`). These shapes are announced before the wiki and folio modules exist.

## 2026-09-22 · AI-009 · propose-workflow 1.1.0 (the engine's words, expand first)
**Kind:** CHANGE (additive; the contraction is scheduled)
**What:** `ProposeWorkflowResponse.statuses[]` gains `name` and `order` beside `label` and `sort_order`, which repeat them and are marked deprecated in the document; `ProposeWorkflowRequest.existing.statuses[]` accepts either spelling (`name` or `label`, `order` or `sort_order` — one of each pair is required; `name` and `order` are read); `transitions[].requires_approval` stays optional, always `false` in a proposal, deprecated (the engine models no approval on a transition; a named approval is a later `CHANGE` on both sides); `terminal` stays as information (the engine treats `done` as the resting class). Capability 1.0.0 → 1.1.0 (prompt v2 asks for the engine's words); `label`, `sort_order` and `requires_approval` are removed at 1.2.0, one version after this entry (`ARCH-004 §6`); no path version moves because nothing breaks.
**Backend must:** send `guard_vocabulary: ["requires_reason"]` (the one guard the engine knows) and the three categories; expand a null `from_key` into one transition per status; set `requires_reason` where a proposal carries `reason_code` or the guard and keep the reason free text; read `order` as the display order and `name` as the display name and never `label`, `sort_order` or `requires_approval`, which go at 1.2.0.

## 2026-09-21 · AI-008 · release-notes, generate-tests, post-mortem
**Kind:** ADD
**What:** `release_notes.run` (`POST /v1/release-notes`, `ReleaseNotesRequest {mode: notes | summary, release {name, version?, target_date?, status?, description?}, changes[] {id, key?, kind, title, description?, status_category, participant?}, audience, language?}` → `ReleaseNotesResponse {sections[] {kind, entries[] {source_id, text}}, highlights[], summary, attention[], in_flight[], empty_reason?, confidence}`); `generate_tests.run` (`POST /v1/generate-tests`, `GenerateTestsRequest {mode: cases | artefacts, story {key?, title, description?}, criteria[] {id, text}, cases[] {id, title, objective?, steps[] {action, expected}}, max_cases, language?}` → `GenerateTestsResponse {cases[] {title, given, when, then, priority, area, covers[], inferred}, gaps[], outline[] {heading, lines[], covers[]}, data_tables[] {name, columns[], rows[][], covers[]}, empty_reason?, confidence}`); `post_mortem.run` (`POST /v1/post-mortem`, `PostMortemRequest {incident {key?, title, severity?, started_at?, resolved_at?, impact?}, timeline[] {id, at, participant?, text}, language?}` → `PostMortemResponse {summary, facts[] {source_id, text}, contributing_factors[] {text, evidence[]}, action_items[] {text, evidence[], confidence}, participants_mentioned[], empty_reason?, confidence}`); `ai.output.invalid` gains the detail `untraceable_entry`; `ai.input.rejected` gains the detail `cases_required`; settings `CAPABILITY_RELEASE_NOTES__*`, `CAPABILITY_GENERATE_TESTS__*`, `CAPABILITY_POST_MORTEM__*`.
**Backend must:** send every source with an id it can resolve back — change ids, criterion ids, existing case ids, timeline entry ids — because every entry the service returns cites one and an entry that cites nothing it sent is refused, never returned partial; send people only as participant tokens (`p1`…`p9999`; a name-like participant is refused at validation) and substitute names back on its side; send `status_category` on every change and expect only done changes in the notes and the rest in `in_flight` (the service lists, never counts); send `audience: customer` for anything a customer reads (no token reaches them); treat `cases[]`, `outline[]`, `data_tables[]`, `action_items[]` and every entry as proposals it creates, ranks and edits — the service creates nothing in any hub; read `gaps` as the criteria left uncovered and `inferred` as a case with no stated criterion behind it; keep facts and analysis apart when rendering a post-mortem (`facts[]` are the timeline restated, `contributing_factors[]` are the service's reading); apply the same `Idempotency-Key`, `capability_version` and `RESTRICTED` rules as for `improve_story.run`. These shapes are what the release, test and incident modules must be able to produce; they are announced before those modules exist.

## 2026-09-21 · AI-007 · propose-workflow, summarize
**Kind:** ADD
**What:** `propose_workflow.run` (`POST /v1/propose-workflow`, `ProposeWorkflowRequest {description, item_type?, allowed_categories[] (todo | in_progress | done), guard_vocabulary[], existing? {statuses[], transitions[]}, language?}` → `ProposeWorkflowResponse {statuses[] {key, label, category, initial, terminal, sort_order}, transitions[] {from_key?, to_key, kind, guards[], requires_approval, reason_code?, rationale}, empty_reason?, confidence}`); `ai.output.invalid` gains the details `workflow_no_initial`, `workflow_no_terminal`, `workflow_unreachable_status`, `workflow_endpoint_unknown`, `workflow_self_loop`, `workflow_guard_unknown`, `workflow_reason_missing`, `workflow_duplicate_status`, `workflow_category_not_allowed`, `workflow_existing_dropped`; `summarize.run` gains the modes `standup` and `digest`, the request fields `window? {from_at, to_at}`, `counts[] {kind, count}` and `items[].kind?`, the response fields `standup[] {participant, done[], doing[], blocked[]}` and `digest[] {kind, count, changes[]}` (additive; empty for the other modes), and `ai.input.rejected` gains the details `window_required` and `counts_required`; settings `CAPABILITY_PROPOSE_WORKFLOW__*`.
**Backend must:** send the workflow engine's own vocabulary on every proposal call — the categories it allows and the guard names it knows — and validate the returned scheme against its engine again before installing anything: the service checks structure (one initial in `todo`, a terminal in `done`, reachability, endpoints, guards from the vocabulary, reason codes on backward, reject and reopen moves), the engine owns the rest (names, permissions, approvals, existing items); treat `statuses[]` and `transitions[]` as a proposal the admin edits, never install unseen; show `empty_reason` rather than retry; for a standup send one item per member update with the member as a token, the window it is asking about, and read `standup[]` back by token; for a digest send the window, one item per change with its `kind`, and `counts[]` for every kind it will show — the service echoes those counts and never counts on its own, so a group with an empty `changes[]` and a non-zero `count` is the backend's own number; items outside `window` are left out and `covered_range` says what was read; apply the same `Idempotency-Key`, `capability_version` and `RESTRICTED` rules as for `improve_story.run`.

## 2026-09-21 · AI-007 · platform (error envelope)
**Kind:** FIX
**What:** the document now declares `components/schemas/ErrorEnvelope` (`error {code, message, details[] {field, code, message}, retry_after_ms?}`, `request_id`) with `ErrorBody`, `ErrorDetail` and the `ErrorCode` enum, and every operation references it from each of its 4xx/5xx statuses (derived from `x-error-codes` plus the platform codes) and from `default`; the framework's `HTTPValidationError` (never returned — the handlers render the envelope with `validation.invalid_input`, 400) is gone from the document. The wire shape did not change; the document now says what the service always did. Streaming: summaries stay synchronous in v1; a streamed summary is not planned — streaming lands with the assistant's contract, once.
**Backend must:** regenerate its client from the document and read every non-200 body as `ErrorEnvelope`; drop any special case for a 422 `HTTPValidationError`; nothing else.

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
