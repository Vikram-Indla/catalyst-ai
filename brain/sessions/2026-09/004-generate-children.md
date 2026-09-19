# 004 — generate-children

**Date:** 2026-09-18 · **Ticket:** AI-004 · **Capability or package:** generate-children, platform/{pipeline,similarity}, evals · **Author:** a contributor

## Read
`ARCH-002 §2` (rules as data), `ARCH-003`, `ARCH-007`, `RULE-001 §1` (the rule of two across
capabilities), `RULE-004`, `RULE-008`; the backend's canonical work-item ADR for the hierarchy
(`theme, initiative, epic, feature, story, task, subtask`, per-organisation type registry). The
previous system's `ai-generate-stories`, `ai-generate-epics`, `ai-suggest-children` and the child
modes of `ai-improve-story` for behaviour: a parent → 3–7 children of a mapped child type, "do not
repeat the existing siblings", JSON with title/description/type; and where they went wrong —
children at the wrong level, repeats of siblings, empty acceptance criteria, auto-creation of the
generated items (a backend decision, not ported).

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-004
Capability:      generate-children v1.0.0 (kind sync; alias text-default; one operation, three targets)
Inputs:          parent_title, parent_description, source_texts[], siblings[].title, focus_hint? · CONFIDENTIAL;
                 hierarchy[], parent_level, child_level?, siblings[].key? · INTERNAL; target, max_items, language? · PUBLIC
Tenant boundary: organization_id on the request; cache key and caps per organisation; no storage rows yet
Provider/model:  gemini · text-default → gemini-2.5-flash (register)
Prompt version:  prompt_v1.md (system, developer with the hierarchy as fenced data, user fields, target:<t> sections)
Eval set:        evals/generate-children v1 · 139 cases (49 stories / 41 epics / 49 children; 12 injection, 6 leakage) · 8 graders
Budget:          p95 latency 8 000 ms · p95 cost 6 000 µ$ · timeout 20 000 ms (= the job line)
Failure mode:    as improve-story, plus ai.output.invalid{hierarchy_violation} on a wrong-level candidate and
                 ai.input.rejected{hierarchy_violation} on a request naming a level that is not the parent's next
Cache:           as improve-story (the whole classified request in the key)
Safety:          the same door and scanners; sibling titles and source texts fenced as data; 12 injection cases
Contract:        generate_children.run (POST /v1/generate-children) ADD; not breaking
Invariants:      INV-007..009, INV-011, INV-018, INV-030..033, INV-037, INV-039, INV-042..044
Blast radius:    PLATFORM (two new platform packages; the shared pipeline runner) — CONTRACT for the backend
Decision level:  2
ADR:             none new
```

## Changed
- `contract/generate_children.py` — request (hierarchy as data, siblings, sources, bounds), `Candidate`, response with `empty_reason`
- `capabilities/generate_children/{descriptor,schema,pipeline,postprocess,routes}.py`, `prompt_v1.md` — the capability; `expected_child_level` at the door, `check_hierarchy` after the schema, `mark_duplicates`, `bound`, `candidate_confidence`
- `platform/pipeline/{stages,door,output}.py` — the shared runner (`Stages`, `run_stages`), the door (`Door`, `admit`), the repair loop (`parse_with_repair`); `improve-story` refactored onto it — the third capability shape arrived with the second, and the `dupl` check would have refused two identical runners (`RULE-001 §1`)
- `platform/similarity/lexical.py` — prefix-stemmed token overlap (Jaccard / containment) and `nearest`; the embedding path replaces it behind the same function
- `config/settings.py` — `capability_generate_children`; `app.py` — the router
- `tools/checks/pipeline.py` — the stage order may be declared through `Stages(...)`; `tools/authored.py` — the stand-in answers generate-children requests; `tools/{evals,evalkit,record}.py` — the typed capability registry
- `evals/generate-children/{set.jsonl,graders.py,thresholds.yaml,README.md}` — set v1
- `tests/fixtures/providers/gemini/generate-children/` — 136 authored fixtures (three cases share a prompt) + `_manifest.json`
- `tests/unit/capabilities/generate_children/**`, `tests/unit/platform/{pipeline,similarity}/**`, `tests/contract/test_generate_children.py`
- `docs/`: `capabilities.md` (three planned rows → one built row), `eval-sets.md`, `config.md`, `contracts-changelog.md` (ADD), `THREAT-003-structured-generation.md`, `06-runbooks/capabilities.md`; `mypy.ini` (each set's graders type-checked on its own — two modules named `graders` by design); `Makefile` (`lint` loops the sets)
- `tools/rules.py` — `DIRECTIVE_BASELINE` 6 → 4 (three test directives removed by typing the tests properly)

## Verify
```
$ make verify
ruff / mypy (183 files + each set's graders) / lint-imports   All checks passed! · Success · Contracts: 5 kept, 0 broken.
tools.checks.gate --skip coverage                             GATE GREEN (44 checks)
tools.api                                                     api\openapi.yaml matches the app
pytest tests/architecture · pytest --cov                      24 passed · 250 passed · Total coverage: 99.88%
tools.checks.gate --only coverage                             GATE GREEN (1 checks)
make evals                                                    -- generate-children v1 - 139 cases
                                                              level_correct 1.000 (1.0) · duplicates_marked 1.000 (1.0) · no_duplicate_candidates 1.000 (1.0)
                                                              criteria_present 1.000 (0.95) · bounds_and_reason 1.000 (0.95) · language_preserved 1.000 (1.0)
                                                              identifiers_kept 1.000 (1.0) · no_forbidden_content 1.000 (1.0) · overall 1.000 (0.97)
                                                              p95 latency 11 ms (budget 8000) · p95 cost 1395 micro-dollars (budget 6000)
                                                              -- improve-story v1 - 52 cases · overall 1.000 · p95 3 ms · 448 micro-dollars
                                                              EVALS GREEN
pip-audit / gitleaks / licences                               No known vulnerabilities found · no leaks found · GATE GREEN
selftest                                                      45/45 checks red on their plant
VERIFY GREEN
```
```
$ make ci     (python:3.12.14-slim, the workflow's steps verbatim)
All checks passed! · GATE GREEN (44 checks) · 250 passed in 45.80s · GATE GREEN (1 checks) · EVALS GREEN · GATE GREEN (1 checks)
selftest: 45/45 checks red on their plant
VERIFY GREEN
```
Planted regressions (each reverted, each red): a fixture whose first candidate is at level `task`
→ the pipeline refuses it (`ai.output.invalid`), the case scores 0 → `EVALS RED` on six floors; the
descriptor's cost budget lowered under the measured 1 395 µ$ → `GATE RED at: budgets`.

## Eval and budget numbers
generate-children set v1, prompt v1, `text-default`: **1.000 on every grader; overall 1.000; p95
latency 11 ms; p95 cost 1 395 µ$** (139 cases; 49 / 41 / 49 per target). Authored fixtures, as for
improve-story: the numbers prove the pipeline, the hierarchy validator, de-duplication, the scanners,
the graders and the budget accounting — not the live model. improve-story unchanged at 1.000.

## Decisions and questions
- D-010 proposed: one capability `generate-children` with a `target` field (`stories`, `epics`,
  `children`) instead of three operations — the same reasoning as `improve-story`'s `mode`: one
  pipeline, one schema, one prompt file with per-target sections, one set with per-target tags; the
  three previous functions retire under it.
- D-011 proposed: a child level is exactly the parent's next in the supplied hierarchy — on the
  request (`ai.input.rejected`, `hierarchy_violation`) and on the output (`ai.output.invalid`,
  `hierarchy_violation`). Stories under an epic in an organisation whose hierarchy has `feature`
  between them are a two-step request the backend makes twice; the service never skips a level.
- D-012 proposed: the shared pipeline runner and door live in `platform/pipeline` (no product
  noun) once the second capability made the shape a rule-of-two case the `dupl` check enforces.
- Q-005: is `theme → initiative → epic → feature → story → task → subtask` the hierarchy every
  organisation gets, or may an organisation disable levels (`feature`)? v1 takes the hierarchy per
  request, so either works; the eval set assumes an organisation without `feature` for the
  `stories` target.
- No finding filed.

## Commit
Two proposals:
1. Files: `src/**`, `tests/{unit,contract}/**`, `evals/generate-children/**`, `tools/**`, `mypy.ini`, `Makefile`, `docs/**`, `brain/**`
   Proposed: `feat(generate-children): typed children at the next level; shared pipeline runner`
2. Files: `api/openapi.yaml`, `tests/fixtures/providers/gemini/generate-children/**`
   Proposed: `gen: contract document and authored fixtures for generate-children v1`
Green light: given by the lead on 2026-09-19 — committed on local `main` in the proposed order (no remote yet)

## Next
The next capability card on the lead's word; the live recording of both sets the moment a key exists.
