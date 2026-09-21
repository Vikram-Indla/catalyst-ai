# 008 — release notes, test generation, post-mortems

**Date:** 2026-09-21 · **Ticket:** AI-008 · **Capability or package:** release-notes, generate-tests, post-mortem, platform/language, evals · **Author:** a contributor

## Read
`ARCH-002 §2`, `ARCH-003`, `RULE-008`; the backend's `ADR-010` (the hub extension tables named
in one line — `incidents.incident_details`, `tests.defect_details`, `releases.change_details` —
with no field list) and `ARCH-001 §2` (the release, test and incident hubs); the previous
system's `release-notes-generate` (a deterministic Markdown fallback plus a prompt over
`rh_releases`, `rh_changes` and the linked `ph_issues`, "do not invent items", a count of what
remains), `summarize-release` (an overview for a lead with a progress percentage and the last 80
items), `ai-generate-story-test-cases` (at most ten cases, 100% coverage of every criterion,
steps with action, test data and expected result; a free-prompt mode), `ai-generate-test-artefacts`
(a second provider, a strict schema with `covers[]` anchors, a `coverage_map` and `gaps`, "do not
invent behaviour"), and `ai-post-mortem` (a business-request retrospective from `profiles` and a
process-step audit log — not an incident post-mortem, `F-014`) for behaviour.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-008
Capability:      release-notes v1.0.0 (notes, summary) · generate-tests v1.0.0 (cases, artefacts) · post-mortem v1.0.0 · alias text-default
Inputs:          release-notes: changes[] {id, key?, kind, title, description?, status_category, participant?} · CONFIDENTIAL;
                 release · INTERNAL; mode, audience, language? · PUBLIC
                 generate-tests: story, criteria[] {id, text}, cases[] {id, title, objective?, steps[]} · CONFIDENTIAL; mode, max_cases,
                 language? · PUBLIC
                 post-mortem: incident, timeline[] {id, at, participant?, text} · CONFIDENTIAL; language? · PUBLIC
Tenant boundary: organization_id on the request; the cache key carries it; no storage rows
Provider/model:  gemini · text-default → gemini-2.5-flash (all three; text-long deferred until a live recording says a timeline
                 of 200 entries needs it)
Prompt version:  prompt_v1.md for each (system, developer with mode sections where there are modes, user fences)
Eval set:        evals/release-notes v1 · 90 cases · 10 graders · evals/generate-tests v1 · 89 cases · 10 graders ·
                 evals/post-mortem v1 · 45 cases · 10 graders
Budget:          release-notes p95 10 000 ms · 6 000 µ$ · generate-tests p95 12 000 ms · 8 000 µ$ · post-mortem p95 12 000 ms ·
                 8 000 µ$ · timeouts 20 000 ms
Failure mode:    as improve-story, plus ai.output.invalid{untraceable_entry} on any entry citing an id the request did not carry
                 (one detail per entry, nothing partial), ai.output.unsafe{participant_not_in_thread} on a token outside the data,
                 ai.input.rejected{cases_required} on artefacts without cases
Cache:           the whole classified request in the key; release-notes 900 s, generate-tests 3 600 s, post-mortem 900 s
Safety:          the door's scanner over every text; fences; the data rules (no invented entry, no name, no credential, no blame);
                 injection cases in every set; the leakage scan over every line; the participant pattern refuses a name at
                 validation
Contract:        release_notes.run, generate_tests.run, post_mortem.run ADD; the ErrorEnvelope referenced from each; not breaking
Invariants:      INV-007..009, INV-011, INV-018, INV-030..033, INV-035, INV-037, INV-039, INV-042, INV-043; new INV-047
Blast radius:    PLATFORM — platform/language/records (the participant rule moved there from summarize, behaviour unchanged) and
                 the branch's earlier document change; CAPABILITY for the three packages; CONTRACT for the backend
Decision level:  2
ADR:             none new
```

## Changed
- `platform/language/records.py` — `tokens_in`, `foreign_tokens`, `refuse_foreign_tokens` (moved from `summarize/postprocess.py`, same detail `participant_not_in_thread`), `untraceable`, `refuse_untraceable` (`untraceable_entry`, the id in the message); `summarize/postprocess.py` now calls it
- `contract/{release_notes,generate_tests,post_mortem}.py` — the three requests with every field classified, people as tokens by pattern, ids on every source; the responses with `source_id` / `covers[]` / `evidence[]` on every entry
- `capabilities/release_notes/**` — sections laid out in the changes' order and only for kinds with entries, highlights ≤ 3 by schema of the prompt, `in_flight` listed from the request (never counted), a customer never reads a token
- `capabilities/generate_tests/**` — `cases_required` at the door for artefacts; cases bounded to `max_cases`; `gaps` computed from the kept cases, never the model's; a case citing nothing without `inferred` refused; tables without a column or a citation dropped
- `capabilities/post_mortem/**` — facts in the timeline's order, one per entry at most; factors without evidence dropped; every citation checked; the participant rule over every line and the model's `participants_mentioned`
- `config/settings.py`, `app.py` — three capability groups, three routers
- `tools/{hub_terms,evalsets_hubs,authored_hubs}.py`, `tools/{authored,evalsets,evalkit}.py` — the vocabulary, the generators, the stand-ins (dispatched on the fence names before the translation marker), the registry rows
- `evals/{release-notes,generate-tests,post-mortem}/{set.jsonl,graders.py,thresholds.yaml,README.md}`, `tests/fixtures/providers/gemini/{release-notes,generate-tests,post-mortem}/`
- `tests/unit/platform/language/test_records.py`, `tests/unit/capabilities/{release_notes,generate_tests,post_mortem}/**`, `tests/unit/contract/test_{release_notes,generate_tests,post_mortem}.py`, `tests/contract/test_{release_notes,generate_tests,post_mortem}.py`
- `docs/`: ledgers (capabilities, errors, config, eval-sets, invariants, contracts changelog), `THREAT-003` rows 13–14, `THREAT-004` rows 12–13, the runbook lines

## Verify
```
$ make verify
ruff / mypy (343 files + each set's graders) / lint-imports   All checks passed! · Success · Contracts: 5 kept, 0 broken.
tools.checks.gate --skip coverage,budgets                     GATE GREEN (43 checks) · report: contract has 13 files (F-015)
tools.api · oasdiff                                           api\openapi.yaml matches the app · no breaking change against main
pytest tests/architecture · pytest --cov                      24 passed · 537 passed in 104.17s · Total coverage: 99.58%
tools.checks.gate --only coverage                             GATE GREEN (1 checks)
pytest tests/storage                                          3 passed
make evals                                                    -- release-notes v1 - 90 cases · 1.000 on every grader · overall 1.000 (0.97) · p95 6 ms · 1 772 micro-dollars
                                                              -- generate-tests v1 - 89 cases · 1.000 on every grader · overall 1.000 (0.97) · p95 5 ms · 2 612 micro-dollars
                                                              -- post-mortem v1 - 45 cases · 1.000 on every grader · overall 1.000 (0.97) · p95 5 ms · 1 716 micro-dollars
                                                              -- propose-workflow · summarize · translate · search · improve-story · generate-children unchanged
                                                              EVALS GREEN
tools.checks.gate --only budgets                              GATE GREEN (1 checks)
pip-audit / gitleaks / licences                               No known vulnerabilities found · no leaks found · GATE GREEN
selftest                                                      45/45 checks red on their plant
VERIFY GREEN
```
```
$ make ci
$ make ci     (python:3.12.14-slim, the workflow's steps verbatim)
All checks passed! · Success: no issues found in 343 source files · Contracts: 5 kept, 0 broken.
GATE GREEN (43 checks) · api/openapi.yaml matches the app · oasdiff: no breaking change against main
24 passed · 537 passed in 183.38s · Total coverage: 99.58% · GATE GREEN (1 checks)
pytest tests/storage: 3 passed
EVALS GREEN (release-notes 1.000 · generate-tests 1.000 · post-mortem 1.000 · propose-workflow 1.000 · summarize 1.000 · translate 1.000 · search recall@10 0.914, mrr 0.787 · improve-story 1.000 · generate-children 1.000) · GATE GREEN (1 checks)
No known vulnerabilities found · no leaks found · GATE GREEN (1 checks)
selftest: 45/45 checks red on their plant
VERIFY GREEN
```

## Eval and budget numbers
release-notes set v1, prompt v1, `text-default`: **1.000 on every grader (schema_valid,
no_invented_entries, done_only_noted, every_done_change_noted, keys_traceable, audience_respected,
highlights_bounded, language_preserved, no_forbidden_content, empty_when_nothing); overall 1.000;
p95 latency 6 ms; p95 cost 1 772 µ$** over 90 cases (45 notes / 45 summary; 16 Arabic; 8
injection; 2 empty).
generate-tests set v1, prompt v1, `text-default`: **1.000 on every grader (schema_valid,
covers_traceable, criteria_covered, given_when_then, bounded, areas_blended, artefacts_shaped,
no_real_data, language_preserved, empty_when_nothing); overall 1.000; p95 latency 5 ms; p95 cost
2 612 µ$** over 89 cases (44 cases / 44 artefacts; 13 with a vague criterion; 8 Arabic; 8
injection; 1 empty).
post-mortem set v1, prompt v1, `text-default`: **1.000 on every grader (schema_valid,
facts_traceable, analysis_evidenced, facts_cover_timeline, tokens_only, blameless, keys_traceable,
language_preserved, no_forbidden_content, empty_when_nothing); overall 1.000; p95 latency 5 ms;
p95 cost 1 716 µ$** over 45 cases (8 Arabic; 4 injection; 1 empty).
Authored fixtures: one entry per done change, one case per criterion, every timeline entry
restated with its id — the numbers prove the pipelines, the traceability rule, the token rule,
the layouts, the bounds and the graders, not the models' prose, test design or analysis.
Planted regressions (each reverted, each red): the release stand-in citing `chg-1x` → every
notes case refused with `untraceable_entry`, `EVALS RED for release-notes`; the test stand-in
citing nothing without `inferred` → every cases case refused, `EVALS RED for generate-tests`;
the incident stand-in citing `ev-0` → every case refused, `EVALS RED for post-mortem`; through
the app, `test_release_notes_run_refuses_an_invented_entry`,
`test_generate_tests_run_refuses_an_untraceable_case` and
`test_post_mortem_run_refuses_untraceable_facts_and_foreign_names` (an invented id → 502
`untraceable_entry`; `p7` in a summary → 502 `participant_not_in_thread`; a name as a participant
→ 400 at validation).

## Decisions and questions
- D-027 proposed: every record entry cites a supplied id or the response is refused; the rule lives once in `platform/language/records`.
- D-028 proposed: the three contracts are designed from the hubs' words and the previous behaviour and announced before the hub modules exist; a post-mortem is the incident hub's timeline.
- F-014: the previous `ai-post-mortem` was a business-request retrospective; F-015: the contract package is reported for a split (thirteen modules) — left as is, revisited with the assistant.
- Q-009 to the backend: what the hub modules can produce for these shapes.

## Commit
Two proposals (after AI-007's two):
1. Files: `src/**`, `tools/**`, `tests/{unit,contract}/**`, `evals/{release-notes,generate-tests,post-mortem}/{graders.py,thresholds.yaml,README.md}`, `docs/**`, `brain/**`
   Proposed: `feat(records): release notes, test generation and post-mortems, every entry traced`
2. Files: `api/openapi.yaml`, `evals/{release-notes,generate-tests,post-mortem}/set.jsonl`, `tests/fixtures/providers/gemini/{release-notes,generate-tests,post-mortem}/**`
   Proposed: `gen: contract document, sets and authored fixtures for the three record capabilities`
Green light: pending the lead

## Next
The backend's answers to `Q-008` and `Q-009`; the live recording of the nine sets when the key arrives; the knowledge card.
