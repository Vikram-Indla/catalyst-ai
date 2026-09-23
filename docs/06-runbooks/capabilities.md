# Capabilities — one line each

What to check when quality drops, how to disable without a deploy, what the backend receives.
Three alerts are about a capability as a whole and land here; the table below is per capability.

## `CapabilityErrorBudgetBurn` — an operation answers `5xx` to more than one call in a hundred

1. `sum by (operation, status) (rate(catalyst_ai_http_requests_total[15m]))` — which operation.
2. `sum by (code) (rate(catalyst_ai_errors_total[15m]))` — the code says whose page it is:
   `ai.provider.*` is `provider-outage.md`, `ai.index.unavailable` is `index-unavailable.md`,
   `auth.origin.unverifiable` is `replay-store-down.md`, `ai.budget.exceeded` is not a `5xx`.
3. The capability's row below for its own checks and its switch. Page severity: a burn that
   continues misses the month's objective.

## `CapabilityLatencyHigh`, `RetrievalLatencyHigh` — an operation's p95 is over its declared budget

Each operation is judged at its capability's `p95_latency_ms` (the rules carry the number as
seconds; `tools/checks/latency` fails the gate when a rule and a descriptor disagree): search
and the index operations 800 ms, `improve-story` and `unfurl` 4 s, `translate` 6 s, generation
and summaries 8 s, `propose-workflow` and `release-notes` 10 s, the assistant, `generate-tests`
and `post-mortem` 12 s, `documents` 15 s. A ticket, not a page.

1. `ProviderLatencyHigh` for the same capability: if it fires too, the provider is the cause
   (`provider-outage.md`).
2. If not, the time is inside the service: for retrieval, the pool (`DATABASE_POOL_MAX` against
   concurrent calls) and the chunk count per organisation; for `documents.ingest`, the parser
   child (`CAPABILITY_DOCUMENTS__TIMEOUT_MS`).
3. The cache: a hit rate that fell (`CacheHitRateLow`) sends every call to the provider.

## `CacheHitRateLow` — the cache serves almost nothing

A collapse means the key moved: a prompt version, a model alias or a capability version changed
the key for every entry, or `cache_ttl_seconds` was lowered. Compare the fall's time with the
last deploy; the rate recovers by itself as the new keys fill. A fall with no deploy means the
backend changed what it sends (a field that varies per call reaching the canonical input).

## Per capability

| Capability | Quality drops: check | Disable | The backend receives when off |
| --- | --- | --- | --- |
| `improve-story` | `make evals --set improve-story` against the fixtures (a red grader names the property); `docs/04-ledgers/eval-sets.md` for the last live numbers; the provider status page and `provider_calls` outcomes per model; `MODEL_TEXT_DEFAULT` for an unplanned model move | `CATALYST_AI_CAPABILITY_IMPROVE_STORY__ENABLED=false` | `503` with `ai.capability.disabled` before any provider call; the backend shows the feature as unavailable and keeps the original text |
| `generate-children` | `make evals --set generate-children` (a red `level_correct` means the model drifted on levels — the pipeline refuses such responses, so users see `ai.output.invalid`, not wrong items; a red `duplicates_marked` means the lexical threshold in `platform/similarity` is off — the tenant's index widens the sibling pool through the retrieve stage, `index_consulted` says whether it took part); the provider status and `provider_calls` outcomes | `CATALYST_AI_CAPABILITY_GENERATE_CHILDREN__ENABLED=false` (`CAPABILITY_SEARCH__ENABLED=false` keeps the capability up without the index) | `503` with `ai.capability.disabled` before any provider call; the backend hides the breakdown action |
| `summarize` | `make evals --set summarize` (a red `tokens_only` means the model names people the thread did not — the pipeline refuses such responses with `ai.output.unsafe`, users see an error, never a name; a red `length_bounds` means the cap in `postprocess.py` and the prompt disagree; a red `digest_shape_and_count_echo` or `window_respected` means `modes.py` stopped echoing the backend's counts or cutting to the window — both are deterministic, so that is a code regression, not a model one); the provider status and `provider_calls` outcomes | `CATALYST_AI_CAPABILITY_SUMMARIZE__ENABLED=false` | `503` with `ai.capability.disabled` before any provider call; the backend hides the summary panel |
| `translate` | `make evals --set translate` (a red `target_script` means the model leaves source-script words — the response's `confidence` and `structure_preserved` already tell the backend; a red `spans_kept` is a prompt regression on keys, links, code or placeholders); the provider status and `provider_calls` outcomes | `CATALYST_AI_CAPABILITY_TRANSLATE__ENABLED=false` | `503` with `ai.capability.disabled` before any provider call; the backend hides the translate action |
| `propose-workflow` | `make evals --set propose-workflow` (a red `structurally_valid` or `every_status_reachable` means the model drifted on the scheme rules — the pipeline refuses such responses with `ai.output.invalid` and one detail per problem, so admins see an error, never a broken scheme; a red `guards_in_vocabulary` means the prompt lost the vocabulary line; a red `no_permission_granted` is an injection regression); the provider status and `provider_calls` outcomes | `CATALYST_AI_CAPABILITY_PROPOSE_WORKFLOW__ENABLED=false` | `503` with `ai.capability.disabled` before any provider call |
| `release-notes` | `make evals --set release-notes` (a red `no_invented_entries` or `done_only_noted` means the model cites changes it was not sent or notes unfinished work — the pipeline refuses the first with `ai.output.invalid`, users see an error, never an invented note; a red `audience_respected` is a prompt regression on tokens for customers); the provider status and `provider_calls` outcomes | `CATALYST_AI_CAPABILITY_RELEASE_NOTES__ENABLED=false` | `503` with `ai.capability.disabled` before any provider call |
| `generate-tests` | `make evals --set generate-tests` (a red `covers_traceable` means cases cite criteria that were not sent — refused with `ai.output.invalid`; a red `criteria_covered` means the prompt lost coverage; a red `no_real_data` is an injection regression on credentials or names); the provider status and `provider_calls` outcomes | `CATALYST_AI_CAPABILITY_GENERATE_TESTS__ENABLED=false` | `503` with `ai.capability.disabled` before any provider call |
| `post-mortem` | `make evals --set post-mortem` (a red `facts_traceable` or `analysis_evidenced` means facts or factors rest on entries that were not sent — refused with `ai.output.invalid`; a red `tokens_only` is refused with `ai.output.unsafe`; a red `blameless` is a prompt regression and the draft still ships — read the summaries by hand until the prompt is fixed); the provider status and `provider_calls` outcomes | `CATALYST_AI_CAPABILITY_POST_MORTEM__ENABLED=false` | `503` with `ai.capability.disabled` before any provider call |
| `documents` (`documents.ingest`, `documents.ask`, `documents.generate`) | `make evals --set documents` (a red `no_uncited_claims` or `citations_resolve` means the model cites what it did not read — the pipeline refuses such answers with `ai.output.invalid`, members see an error, never an invented sentence; a red `not_found_on_traps` means the model answers from outside the passages — a prompt regression); `make evals --set documents-ingest` red means a parser or a guard changed: read the reason class per sample in `tests/fixtures/documents/hostile/`; a parser child that keeps timing out on real files is a budget question (`CAPABILITY_DOCUMENTS__TIMEOUT_MS`) before it is a parser question; `/readyz` `storage: false` means the index is unreachable (`ai.index.unavailable`) | `CATALYST_AI_CAPABILITY_DOCUMENTS__ENABLED=false` | `503` with `ai.capability.disabled` before any parse, embedding or call |
| `assistant` (`assistant.turn`, `assistant.turn_sync`) | `make evals --set assistant` (a red `no_uncited_claims` or `citations_resolve` means the model cites what it was not shown — refused with `ai.output.invalid`, the member sees the error frame, never an invented sentence; a red `not_found_on_traps` or `injection_inert` is a prompt regression); a stream that closes without `done` or `error` is a defect of the writer, never of the model (`tests/contract/test_assistant.py`), and the backend treats it as `ai.provider.unavailable`; `/readyz` `storage: false` means the spaces cannot be read (`ai.index.unavailable`) while turns without spaces still answer | `CATALYST_AI_CAPABILITY_ASSISTANT__ENABLED=false` | `503` with `ai.capability.disabled` before any retrieval or call; a stream not yet open returns the envelope, never a frame |
| `unfurl` (`unfurl.run`) | `make evals --set unfurl` (a red `facts_carried` means a fact left the service that the text does not carry — the postprocess drops those, so it is a pipeline defect, not a prompt one) | `CATALYST_AI_CAPABILITY_UNFURL__ENABLED=false` | `503` with `ai.capability.disabled` |
| `search` (`index.upsert`, `index.delete`, `search.run`) | `make evals` (the `search` set runs against a real PostgreSQL; a red `tenant_isolation` is an incident, stop everything; a red `recall_at_10` after a model move means `catalyst-ai reembed` has not finished — `docs/06-runbooks/index-rebuild.md`); `/readyz` `storage: false` means the pool cannot reach the database (`ai.index.unavailable` on every operation); `provider_calls` rows under `search` for embedding spend; the chunk count per organisation against `RETRIEVAL_INDEX_MAX_CHUNKS_PER_ORGANIZATION` | `CATALYST_AI_CAPABILITY_SEARCH__ENABLED=false` | `503` with `ai.capability.disabled` on all three operations; `generate-children` skips its retrieve stage; the backend hides similar-items and semantic search and keeps indexing for later (upserts also refuse while off — it re-sends on a rebuild) |
