# 01 — Status

Living state of the AI service. Rewritten, not appended. Last updated: 2026-09-18 (session 004).

## Where we are

The constitution (`docs/`) and the scaffold under it (the kernel, the port, 45 checks, hooks, `make ci`) are written and await the lead's
adoption (`D-001`). No remote exists; the lead commits to local `main`. The work runs in four
phases; the first capability is chosen by consumer pressure — the backend's work-items module
needs `improve-story` first.

| Phase | Goal | Done when |
| --- | --- | --- |
| 1 — Freeze the constitution | `RULE-000..009`, `ARCH-001..012`, `ADR-001..007`, the ledgers, the invariants registry | The lead signs off; `D-001` records it. **In review with AI-002.** |
| 2 — Build the enforcement engine | the scaffold: `uv`, FastAPI health, the port with the recorded transport, `tools/checks` with a plant per row of `RULE-006`, `.githooks`, `make verify`, `make ci`, the drift check | `make tools && make hooks && make verify` green from a clean clone; every check red on its plant (AI-002). **Built; in review.** |
| 3 — Build the golden capability | `improve-story` complete: contract, eval set, prompt v1, pipeline, adapter, budgets, safety cases, contract tests, runbook line, threat model; announced to the backend | Every row of `RULE-004 §3` exists for it; the backend's generated client calls it (AI-003). **Built on authored fixtures; in review; live recording pending a key.** |
| 4 — Scale | Capabilities in the ledger's order under `RULE-007`: ticket → impact matrix → eval set → contract → pipeline → gate → record → review → merge; each retiring its previous functions | Each lands with its eval numbers, its threat model row, its runbook line, and no finding open against the pattern |

## Tickets

| ID | Title | Capability or package | Names | Retires | Evidence required | State |
| --- | --- | --- | --- | --- | --- | --- |
| AI-001 | The constitution: `ENGINEERING.md`, `docs/`, `brain/` in the backend's shape | docs | all | — | the lead's review; every rule with an enforcement row; every previous function in the ledger | review (session 001) |
| AI-002 | The scaffold under the law: `uv`, FastAPI health, the `Provider` port and recorded transport, settings, `tools/checks` + selftest, `.githooks`, `make verify`, `make ci`, the OpenAPI drift check, Dockerfile, compose with `pgvector` | platform, providers/port, tools | ARCH-011, ARCH-012, RULE-006 | — | `make tools && make hooks && make verify` green from clean clone; selftest red on every plant; hook transcripts; `make ci` green; drift check red on a plant | review (session 002) |
| AI-003 | Contract v1 and the golden capability `improve-story`: the first adapter, the eval harness and set, prompt v1, budgets, safety cases, contract tests, runbook line, THREAT-002; announced to the backend | improve-story, providers/gemini, evals | ARCH-003..005, ARCH-007..009, RULE-003, RULE-004, RULE-008 | `ai-improve-story` (rewrite modes) | eval numbers pasted and above floors (authored fixtures); budgets met; contract test per error code; injection and leakage cases; `make verify` and `make ci` | review (session 003) |
| AI-004 | Structured generation as one capability `generate-children` (targets stories, epics, children): hierarchy-aware candidates validated against the supplied levels, sibling de-duplication, per-target eval cases | generate-children, platform/{pipeline,similarity}, evals | ARCH-003, RULE-001 §1, RULE-008 | `ai-generate-stories`, `ai-generate-epics`, `ai-suggest-children`, `ai-improve-story` child modes | eval numbers pasted (authored fixtures); hierarchy violation refused on request and output; `make verify` and `make ci` | review (session 004) |

Capabilities after AI-004, in the ledger's order: retrieval (`similar-items`, `search-items`),
summaries and translation, workflow and digests, release/test/incident, knowledge, the assistant,
then the retirement pass.

## Blocked

Nothing. Open questions that shape later tickets: `Q-001` (participant labels), `Q-002`
(quality sampling opt-in).

## Next

The lead reviews `docs/`, the scaffold, `improve-story` and `generate-children`; on adoption `D-001..D-012` are recorded; a provider key unlocks the live recording of both sets; the next capability card follows.
