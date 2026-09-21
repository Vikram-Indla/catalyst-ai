# 01 — Status

Living state of the AI service. Rewritten, not appended. Last updated: 2026-09-21 (session 008).

## Where we are

The constitution, the scaffold, `improve-story` and `generate-children` are on local `main`
(seven commits, 2026-09-19; `D-001` still to be recorded by the lead). No remote exists. The
retrieval package (AI-005) and the summaries and translation capabilities (AI-006) are built in
the working tree: the service's own database with RLS, the `search` capability and its index
operations, the re-embed and retention jobs, the retrieval eval against a real PostgreSQL;
`summarize` with the participant-token rule and `translate` with structure kept; then (AI-007)
`propose-workflow` and the `standup` and `digest` modes, with the error envelope in the
document; then (AI-008) `release-notes`, `generate-tests` and `post-mortem` with every entry
traced to a supplied id. The work runs in four phases; phase 4 is under way.

| Phase | Goal | Done when |
| --- | --- | --- |
| 1 — Freeze the constitution | `RULE-000..009`, `ARCH-001..012`, `ADR-001..007`, the ledgers, the invariants registry | The lead signs off; `D-001` records it. **In review with AI-002.** |
| 2 — Build the enforcement engine | the scaffold: `uv`, FastAPI health, the port with the recorded transport, `tools/checks` with a plant per row of `RULE-006`, `.githooks`, `make verify`, `make ci`, the drift check | `make tools && make hooks && make verify` green from a clean clone; every check red on its plant (AI-002). **Built; in review.** |
| 3 — Build the golden capability | `improve-story` complete: contract, eval set, prompt v1, pipeline, adapter, budgets, safety cases, contract tests, runbook line, threat model; announced to the backend | Every row of `RULE-004 §3` exists for it; the backend's generated client calls it (AI-003). **Built on authored fixtures; in review; live recording pending a key.** |
| 4 — Scale | Capabilities in the ledger's order under `RULE-007`: ticket → impact matrix → eval set → contract → pipeline → gate → record → review → merge; each retiring its previous functions | Each lands with its eval numbers, its threat model row, its runbook line, and no finding open against the pattern |

## Tickets

| ID | Title | Capability or package | Names | Retires | Evidence required | State |
| --- | --- | --- | --- | --- | --- | --- |
| AI-001 | The constitution: `ENGINEERING.md`, `docs/`, `brain/` in the backend's shape | docs | all | — | the lead's review; every rule with an enforcement row; every previous function in the ledger | done (session 001; on `main` 2026-09-19) |
| AI-002 | The scaffold under the law: `uv`, FastAPI health, the `Provider` port and recorded transport, settings, `tools/checks` + selftest, `.githooks`, `make verify`, `make ci`, the OpenAPI drift check, Dockerfile, compose with `pgvector` | platform, providers/port, tools | ARCH-011, ARCH-012, RULE-006 | — | `make tools && make hooks && make verify` green from clean clone; selftest red on every plant; hook transcripts; `make ci` green; drift check red on a plant | done (session 002; on `main` 2026-09-19) |
| AI-003 | Contract v1 and the golden capability `improve-story`: the first adapter, the eval harness and set, prompt v1, budgets, safety cases, contract tests, runbook line, THREAT-002; announced to the backend | improve-story, providers/gemini, evals | ARCH-003..005, ARCH-007..009, RULE-003, RULE-004, RULE-008 | `ai-improve-story` (rewrite modes) | eval numbers pasted and above floors (authored fixtures); budgets met; contract test per error code; injection and leakage cases; `make verify` and `make ci` | done (session 003; on `main` 2026-09-19) |
| AI-004 | Structured generation as one capability `generate-children` (targets stories, epics, children): hierarchy-aware candidates validated against the supplied levels, sibling de-duplication, per-target eval cases | generate-children, platform/{pipeline,similarity}, evals | ARCH-003, RULE-001 §1, RULE-008 | `ai-generate-stories`, `ai-generate-epics`, `ai-suggest-children`, `ai-improve-story` child modes | eval numbers pasted (authored fixtures); hierarchy violation refused on request and output; `make verify` and `make ci` | done (session 004; on `main` 2026-09-19) |
| AI-006 | Summaries and translation: `summarize` (modes comments, thread) with participant tokens as a schema rule, the length cap and `covered_range`; `translate` (modes field, title) with a required target, structure and kept spans, language detection | summarize, translate, platform/language, evals | ARCH-003, ARCH-009, RULE-004, RULE-008 | `summarize-comments`, `ai-translate-field`, `ai-translate-title`, `ai-improve-story` mode `translate_text` | no participant outside the tokens (refused on output); the cap and the range; the target required; Markdown preserved; sets ≥ 40 per mode with numbers (authored fixtures); `make verify` and `make ci` | review (session 006) |
| AI-005 | Retrieval: the storage seam over the service's own PostgreSQL with `pgvector` and RLS, the `work_items` corpus (chunking, versioned embeddings), hybrid search with reciprocal rank fusion, the `search` capability (`index.upsert`, `index.delete`, `search.run`), the re-embed and retention jobs, the labelled retrieval set, `generate-children` de-duplication over the index | search, retrieval, platform/storage, providers/gemini (embed), evals | ARCH-006, ARCH-007 §4, ADR-006, RULE-005 | `ai-similar-items`; the semantic half of `ai-search-issues` | RLS proven with the application layer bypassed; versions never mixed; fusion documented; recall@10 and MRR pasted (authored fixtures, real database); index budget and oversized document refused; injection and cross-tenant cases; `make verify` and `make ci` | review (session 005) |

| AI-007 | Workflow proposals, standups and digests: `propose-workflow` (a described process → a structurally valid scheme the backend validates against its engine; reachability, the single initial, the guard vocabulary, reasons where implied); `summarize` modes `standup` and `digest` (the window cut, tokens only, counts echoed); the `ErrorEnvelope` schema referenced from every operation's error statuses (FIX); `ARCH-003 §1` reworded to one concern per package (`D-023`) | propose-workflow, summarize, platform/httpserver, evals | ARCH-002 §2, ARCH-003, ARCH-004, RULE-003, RULE-008 | `workflow-ai`, `ai-generate-workflow`, `standup-summarize`, `standup-summary`, `ai-digest` | the validator on planted proposals; both sets ≥ 40 per operation and mode with numbers; the document with the envelope and no drift; the record | built (session 007), awaiting the lead's review |

| AI-008 | Release, test and incident capabilities: `release-notes` (notes, summary), `generate-tests` (cases, artefacts), `post-mortem`; every entry traced to a supplied id (`untraceable_entry`), people as tokens, facts apart from analysis; the record rules in `platform/language/records` | release-notes, generate-tests, post-mortem, platform/language, evals | ARCH-002 §2, ARCH-003, RULE-008 | `release-notes-generate`, `summarize-release`, `ai-generate-story-test-cases`, `ai-generate-test-artefacts`, `ai-post-mortem` | the traceability refusal on recorded bad outputs; three sets ≥ 40 per mode with numbers; the document with drift green; the record | built (session 008), awaiting the lead's review |

Capabilities after AI-008, in the ledger's order: knowledge, the assistant, then the
retirement pass.

## Blocked

Nothing. Open questions that shape later tickets: `Q-001` (participant labels), `Q-002`
(quality sampling opt-in), `Q-007` (the backend's `kind` vocabulary and indexing events),
`Q-008` (the workflow engine's field list and guard vocabulary), `Q-009` (what the hub
modules can produce for the three record contracts).

## Next

The lead reviews AI-007 and AI-008 (`D-023..D-028`, `F-012..F-015`, `Q-008`, `Q-009`); a provider key unlocks the live recording of the nine sets (`make record LIVE=1 CAP=search` needs a database too); the knowledge card follows.
