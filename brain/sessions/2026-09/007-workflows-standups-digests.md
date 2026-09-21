# 007 — workflow proposals, standups and digests

**Date:** 2026-09-21 · **Ticket:** AI-007 · **Capability or package:** propose-workflow, summarize, platform/httpserver, evals · **Author:** a contributor

## Read
`ARCH-002 §2` (the service proposes, the backend validates and installs), `ARCH-003` (reworded
here, `D-023`), `ARCH-004 §3`, `RULE-003`, `RULE-008`; the backend's `ADR-010` — one sentence on
the workflow engine ("statuses, transitions, guards, approvals, reason codes"), no field list
(`F-012`), and `ARCH-012` (`workflow_*` tables under `admin`); the lead's answers: one concern
per package, no streamed summaries in v1, the error envelope as a `FIX` before this ticket; the
backend's note that the document had no `ErrorEnvelope` schema. The previous system's
`ai-generate-workflow` (a grammar of eleven rules mirrored from a database validator: exactly one
initial in `todo`, at least one terminal in `done`, endpoints exist, no self-loop, every status
reachable, backward/reject/reopen with a reason, at most 25 statuses), `workflow-ai` (a
conversational proposal with questions, violations and add/remove deltas — the conversation stays
with the backend), `standup-summarize` and `standup-summary` (per-member recaps with names from
the profiles table, "ground truth only", 2–4 sentences) and `ai-digest` (612 lines reading seven
tables, scoring by role, counting, and "use only the data provided, never invent counts") for
behaviour.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-007
Capability:      propose-workflow v1.0.0 (alias text-default) · summarize v1.0.0 gains modes standup, digest · platform: the document
Inputs:          propose-workflow: description · CONFIDENTIAL; item_type?, allowed_categories[], guard_vocabulary[], existing? · INTERNAL; language? · PUBLIC
                 summarize (new): items[].kind?, window? {from_at, to_at}, counts[] {kind, count} · INTERNAL
Tenant boundary: organization_id on the request; the cache key carries it; no storage rows
Provider/model:  gemini · text-default → gemini-2.5-flash (both)
Prompt version:  propose-workflow prompt_v1.md (system, developer, user fences description and existing) · summarize prompt v1 gains
                 Window and Counts lines and the mode:standup, mode:digest sections (prompt version unchanged: v1 had no live
                 recording yet; the authored fixtures are re-recorded)
Eval set:        evals/propose-workflow v1 · 46 cases · 13 graders · evals/summarize v1 · 198 cases (+92) · 14 graders (+4)
Budget:          propose-workflow p95 10 000 ms · 6 000 µ$ · timeout 20 000 ms · summarize unchanged (8 000 ms · 4 000 µ$)
Failure mode:    as improve-story, plus ai.output.invalid{workflow_*} on a scheme the engine could not take (one detail per problem,
                 nothing partial) and ai.input.rejected{window_required | counts_required} at the door of the window modes;
                 ai.output.unsafe{participant_not_in_thread} now covers every standup and digest line
Cache:           the whole classified request in the key (the window-cut request for the window modes); propose-workflow 600 s
Safety:          the door's scanner over the description and the existing scheme text, over every item; fences; the data rule
                 names permissions and roles as out of scope; injection cases in both sets ("also grant admin", an item text
                 posing as an instruction); the leakage scan over labels, rationales and every line
Contract:        propose_workflow.run (POST /v1/propose-workflow) ADD; summarize.run gains two mode values and additive fields;
                 components/schemas/ErrorEnvelope referenced from every operation's 4xx/5xx and default (FIX — the wire shape
                 never changed); HTTPValidationError gone from the document; not breaking (oasdiff)
Invariants:      INV-007..009, INV-011, INV-018, INV-030..033, INV-035, INV-037, INV-039, INV-042, INV-043; new INV-045, INV-046
Blast radius:    SYSTEM (the document's error responses touch every operation; ARCH-003 reworded; a check rule narrowed);
                 CONTRACT for the backend
Decision level:  2
ADR:             none new
```

## Changed
- `platform/httpserver/document.py` — `with_error_responses`: the envelope's schemas declared once, one response per error status derived from `x-error-codes` plus the platform codes, a `default`; the framework's `HTTPValidationError` dropped; `app.py` renders through it
- `docs/01-architecture/ARCH-003` §1 reworded to one concern per package (1.0.1, `D-023`); the changelog `FIX` entry with the streaming note (`D-024`)
- `contract/propose_workflow.py` — `Status`, `Transition`, `Scheme`, the request (categories must hold `todo` and `done`, no repeats) and the response
- `capabilities/propose_workflow/{descriptor,schema,scheme,postprocess,pipeline,routes}.py`, `prompt_v1.md` — `scheme.py`: the structural rules (duplicates, the single initial in `todo`, a terminal in `done`, allowed categories, existing statuses kept, endpoints, self-loops, guards from the vocabulary, reasons on backward/reject/reopen, reachability by walk from the initial with a null `from_key` leaving every status); `postprocess.py`: the refusal with every detail, a deterministic confidence (size, dead ends, no `in_progress`), the empty proposal
- `contract/summarize.py` — modes `standup`, `digest`; `items[].kind?`, `Window`, `KindCount`, `StandupEntry`, `DigestGroup`; additive response fields
- `capabilities/summarize/modes.py` — `require_window` at the door, `within_window` in stage 1, the shapes laid out from the request (one entry per token in the window; one group per counted kind with the request's count), `clean_lines`; `schema.py` gains the model's `standup`/`digest` shapes and `prose_of` for the scan; `postprocess.py` checks tokens over every line; `prompt_v1.md` gains the window and counts lines and two mode sections
- `config/settings.py`, `app.py` — the `propose_workflow` group and router
- `tools/rules.py` — `PRODUCT_TABLE_PREFIXES` narrowed to the previous system's real table names (`F-013`)
- `tools/{workflow_terms,evalsets_workflow,authored_workflow,window_terms,evalsets_windows,authored_windows}.py`, `tools/{authored,authored_threads,evalsets,evalsets_threads,evalkit}.py` — the generators, the stand-ins, the registry row
- `evals/propose-workflow/{set.jsonl,graders.py,thresholds.yaml,README.md}`, `evals/summarize/{set.jsonl,graders.py,thresholds.yaml}`, `tests/fixtures/providers/gemini/{propose-workflow,summarize}/`
- `tests/unit/platform/httpserver/test_document.py`, `tests/unit/capabilities/propose_workflow/**`, `tests/unit/capabilities/summarize/test_modes.py` (+ pipeline and conftest), `tests/unit/contract/test_propose_workflow.py`, `tests/contract/test_propose_workflow.py`, `tests/contract/test_summarize.py`
- `docs/`: ledgers (capabilities, errors, config, eval-sets, invariants, contracts changelog ×2), `THREAT-003` rows 10–12, `THREAT-004` rows 10–11, the runbook lines

## The proposal schema against `ADR-010` (the card's table)
| `ADR-010` word | Proposal field | Structural rule the service checks | Left to the engine |
| --- | --- | --- | --- |
| statuses | `statuses[] {key, label, category, initial, terminal, sort_order}` | unique keys; exactly one `initial` and it is `todo`; ≥ 1 `terminal` in `done`; categories from `allowed_categories`; every status reachable; an `existing` status never dropped; ≤ 25 | names, colours, who may see them |
| transitions | `transitions[] {from_key?, to_key, kind, rationale}` | endpoints exist; no self-loop; `from_key` null = from any | ordering, screens, notifications |
| guards | `guards[]` | every name in the request's `guard_vocabulary` | what a guard evaluates to |
| approvals | `requires_approval` | — (a boolean; `Q-008` asks whether a named approval is wanted) | who approves |
| reason codes | `reason_code?` | present on `backward`, `reject`, `reopen` | the reason list an admin maintains |

## Verify
```
$ make verify
ruff / mypy (296 files + each set's graders) / lint-imports   All checks passed! · Success · Contracts: 5 kept, 0 broken.
tools.checks.gate --skip coverage,budgets                     GATE GREEN (43 checks)
tools.api · oasdiff                                           api\openapi.yaml matches the app · no breaking change against main
pytest tests/architecture · pytest --cov                      24 passed · 456 passed in 65.78s · Total coverage: 99.51%
tools.checks.gate --only coverage                             GATE GREEN (1 checks)
pytest tests/storage                                          3 passed
make evals                                                    -- propose-workflow v1 - 46 cases · 1.000 on every grader · overall 1.000 (0.97) · p95 10 ms · 1 595 micro-dollars
                                                              -- summarize v1 - 198 cases · 1.000 on every grader · overall 1.000 (0.97) · p95 18 ms · 1 028 micro-dollars
                                                              -- search v1 · improve-story v1 · generate-children v1 · translate v1 unchanged
                                                              EVALS GREEN
tools.checks.gate --only budgets                              GATE GREEN (1 checks)
pip-audit / gitleaks / licences                               No known vulnerabilities found · no leaks found · GATE GREEN
selftest                                                      45/45 checks red on their plant
VERIFY GREEN
```
```
$ make ci
$ make ci     (python:3.12.14-slim, the workflow's steps verbatim)
All checks passed! · Success: no issues found in 296 source files · Contracts: 5 kept, 0 broken.
GATE GREEN (43 checks) · api/openapi.yaml matches the app · oasdiff: no breaking change against main
24 passed · 456 passed in 88.16s · Total coverage: 99.51% · GATE GREEN (1 checks)
pytest tests/storage: 3 passed
EVALS GREEN (propose-workflow 1.000 · summarize 1.000 · translate 1.000 · search recall@10 0.914, mrr 0.787 · improve-story 1.000 · generate-children 1.000) · GATE GREEN (1 checks)
No known vulnerabilities found · no leaks found · GATE GREEN (1 checks)
selftest: 45/45 checks red on their plant
VERIFY GREEN
(one earlier run of the same target stopped at pip-audit: the container could not resolve pypi.org for a minute; the re-run above passed unchanged)
```

## Eval and budget numbers
propose-workflow set v1, prompt v1, `text-default`: **1.000 on every grader (schema_valid,
structurally_valid, single_initial_and_terminal, every_status_reachable, guards_in_vocabulary,
rationale_present, reasons_where_implied, stages_covered, existing_kept, no_forbidden_content,
no_permission_granted, empty_when_vague, language_followed); overall 1.000; p95 latency 10 ms;
p95 cost 1 595 µ$** over 46 cases (6 families × plain / guards / existing / two categories /
Arabic / guards outside the vocabulary; 6 injection; 4 vague).
summarize set v1, prompt v1, `text-default`: **1.000 on every grader (the ten of session 006 plus
standup_shape, digest_shape_and_count_echo, window_respected, no_counts_invented); overall 1.000;
p95 latency 18 ms; p95 cost 1 028 µ$** over 198 cases (58 comments / 48 thread / 46 standup /
46 digest; 36 Arabic; 12 empty; 24 with items outside the window; 16 injection). The 106 cases
of session 006 are unchanged and still 1.000. Authored fixtures: sentence patterns laid out as a
scheme; cue-split standups; kind-grouped digests — the numbers prove the validator, the vocabulary
and reason rules, the window cut, the count echo, the participant rule over every line, the
scanners and the graders, not the model's reading of an admin's prose.
Planted regressions (each reverted, each red): the stand-in emitting guards outside the
vocabulary → 4 cases refused with `workflow_guard_unknown`, every floor 0.913, `EVALS RED for
propose-workflow`; the stand-in dropping reason codes → 42 of 46 refused with
`workflow_reason_missing`, every floor 0.087; `digest_groups` counting the lines instead of
echoing the request → `digest_shape_and_count_echo 0.778`, `EVALS RED for summarize`; the window
cut removed → the prompts change and every standup case misses its fixture (the unit test
`test_within_window_keeps_only_what_the_span_covers` is the direct proof); a proposal with an
unreachable status and a backward move without a reason → `ai.output.invalid` with both details
in `test_propose_workflow_run_refuses_a_scheme_the_engine_could_not_take`; a standup entry for
`p9` → `ai.output.unsafe` in `test_a_standup_names_every_token_and_refuses_a_foreign_one`.

## Decisions and questions
- D-023 (the lead's answer to `Q-006`): one concern per package; `ARCH-003 §1` reworded.
- D-024 (the lead): no streamed summary in v1; streaming lands with the assistant, said in the changelog.
- D-025 proposed: the proposal schema from `ADR-010`'s words and the previous grammar; announced to the backend as a proposal (`Q-008`).
- D-026 proposed: standup and digest are `summarize` modes; the window cut and the count echo are deterministic.
- F-012: `ADR-010` has no field list for the engine. F-013: two table prefixes flagged mode words; narrowed.
- Q-008 to the backend: the engine's field list, guard vocabulary and the shape of approvals.

## Commit
Two proposals:
1. Files: `src/**`, `tools/**`, `tests/{unit,contract}/**`, `evals/{propose-workflow,summarize}/{graders.py,thresholds.yaml,README.md}`, `docs/**`, `brain/**`
   Proposed: `feat(workflows): propose-workflow, standup and digest modes, the error envelope`
2. Files: `api/openapi.yaml`, `evals/{propose-workflow,summarize}/set.jsonl`, `tests/fixtures/providers/gemini/{propose-workflow,summarize}/**`
   Proposed: `gen: contract document, sets and authored fixtures for propose-workflow, summarize`
Green light: pending the lead

## Next
The backend's answer to `Q-008` (a rename is a `CHANGE` before it consumes the operation); the live recording of the six sets when the key arrives; the release, test and incident card.
