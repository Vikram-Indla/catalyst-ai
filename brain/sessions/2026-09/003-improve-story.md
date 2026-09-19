# 003 — improve-story

**Date:** 2026-09-18 · **Ticket:** AI-003 · **Capability or package:** improve-story, providers/gemini, platform/{safety,budgets,cache,resilience,observability,prompts,runtime}, evals · **Author:** a contributor

## Read
`ARCH-003`, `ARCH-004`, `ARCH-005`, `ARCH-007`, `ARCH-008`, `ARCH-009`, `RULE-003`, `RULE-004`,
`RULE-008`, `ADR-004`, `ADR-005`, `ADR-007`. The previous system's `ai-improve-story` for its
behaviour: six editorial modes (`improve_clarify` conservative by default — 0–5% change on good
text; `expand_detail`; `add_acceptance_criteria` as Given/When/Then; `convert_user_story`;
`shorten_focus`; `add_edge_cases`), a per-type focus table, a refusal list (return the text
unchanged), the data-not-instruction rule; and `ai-improve-comment` for its language-preservation
rule. Not ported: the hard-coded English, the tenant-specific persona in the prompt, the reads of
`ai_usage_log`, the gateway.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-003
Capability:      improve-story v1.0.0 (kind sync; alias text-default)
Inputs:          title, description, acceptance_criteria?, focus_hint?, parent_title?, parent_description? · CONFIDENTIAL;
                 item_type · INTERNAL; mode, language?, organization_id, capability_version · PUBLIC/INTERNAL
Tenant boundary: organization_id on the request; cache key and idempotency key carry it; tenant caps per organisation;
                 storage rows: none yet (in-process cache and counters until the storage package)
Provider/model:  gemini · text-default → gemini-2.5-flash (register); MODEL_TEXT_DEFAULT may override with a register id
Prompt version:  prompt_v1.md (header; sections: system, developer, user fields, operation:<mode>, focus:<type>)
Eval set:        evals/improve-story v1 · 52 cases (6 injection, 3 leakage) · 7 deterministic graders · floors in thresholds.yaml
Budget:          p95 latency 4 000 ms · p95 cost 2 000 µ$ · timeout 10 000 ms (≤ the 20 s job line)
Failure mode:    ai.contract.version_mismatch, ai.capability.disabled, ai.input.rejected|too_large, ai.budget.exceeded,
                 ai.provider.unavailable|timeout|rejected|quota, ai.output.invalid|unsafe — each an envelope, never a partial result
Cache:           sha256(org · capability · versions · alias · canonical input), TTL 3 600 s (settings may override); Idempotency-Key scoped by org
Safety:          input scanner (7 RESTRICTED patterns, control sequences, total size); fences with marker stripping; output scanner
                 (foreign keys, unrequested links, secrets, fence echo); 6 injection and 3 leakage eval cases; unit and contract tests
Contract:        improve_story.run (POST /v1/improve-story) ADD; not breaking; changelog entry with the "backend must" lines
Invariants:      INV-007, INV-008, INV-009, INV-011..013, INV-015..019, INV-023, INV-027, INV-030..037, INV-039, INV-042..044
Blast radius:    PLATFORM (platform packages and the first adapter) — CONTRACT for the backend
Decision level:  2 — the first capability under the adopted ADRs; no new ADR
ADR:             none new (ADR-004, ADR-005, ADR-007 applied)
```

## Changed
- `contract/improve_story.py` — the request (every field classified, sizes, BCP 47 language) and the response
- `contract/errors.py` — codes reduced to the ones something raises (the errors check refuses declared-but-unraised); the six deferred codes are named in the ledger
- `config/settings.py` — `CapabilitySettings` (enabled, cache TTL, timeout), `capability_improve_story`, `provider_gemini_api_key`, `provider_gemini_base_url`, `model_text_default`; nested env keys with `__`
- `platform/safety/{delimit,input,output}.py` — fences, the input scanner, the output scanner
- `platform/budgets/tenant.py` — daily spend counter and concurrency slots per organisation (in-process until storage)
- `platform/cache/{key,memory}.py` — the key rule, the `Cache` seam, the in-process cache
- `platform/resilience/{breaker,retry}.py` — the breaker (closed → open → half-open), bounded jittered retries
- `platform/observability/calls.py` — the provider-call row (no content field) and its log line
- `platform/prompts/file.py` — versioned prompt files: header, sections, placeholder filling without f-strings
- `platform/runtime/context.py` — the five seams a pipeline receives
- `providers/port.py` — `request_id` on the generate request; `providers/faults.py` — the scripted fault transport
- `providers/gemini/{adapter,models,errors,aliases}.py` — the adapter over the REST API (deadline, retries, breaker per model, cost from usage, error mapping, structured output), the register rows, alias resolution
- `capabilities/improve_story/{descriptor,schema,pipeline,postprocess,quality,routes}.py`, `prompt_v1.md` — the golden capability
- `evals/improve-story/{set.jsonl,graders.py,thresholds.yaml,README.md}` — set v1
- `tools/{evalkit,evals,record,authored}.py` — the harness, the recorder (`--authored` / `--live`), the stand-in
- `tools/checks/{prompts,pipeline,structure,config,errors}.py` — docstrings are not prompts; source-ordered stage detection; cache dirs skipped; nested config groups; unraised codes refused once a capability exists
- `tests/fixtures/providers/gemini/improve-story/` — 52 authored fixtures + `_manifest.json`
- `tests/unit/**` (21 modules), `tests/contract/test_improve_story.py` (12 tests: every listed code, two organisations, the switch)
- `.importlinter` — `providers.port` as its own layer under `platform`; `ARCH-012 §1` says so
- `Makefile` — `record`, `coverage-check` after `test`; `lint` skips the coverage row
- `docs/`: `capabilities.md` (row built), `eval-sets.md` (row), `providers.md` (rows filled), `errors.md`, `config.md`, `contracts-changelog.md` (ADD), `THREAT-002-rewrite.md`, `06-runbooks/capabilities.md`, `RULE-006 §3` (commands)

## Verify
```
$ make verify
ruff format --check / ruff check                      All checks passed!
mypy src tools tests                                   Success: no issues found in 160 source files
lint-imports                                           Contracts: 5 kept, 0 broken.
tools.checks.gate --skip coverage                      GATE GREEN (44 checks)
tools.api                                              api\openapi.yaml matches the app
pytest tests/architecture                              24 passed
pytest --cov                                           202 passed · Total coverage: 99.69%
tools.checks.gate --only coverage                      GATE GREEN (1 checks)
storage                                                no migrations yet, nothing to test
make evals                                             -- improve-story v1 - 52 cases
                                                       schema_valid 1.000 (floor 1.0) · length_bounds 1.000 (0.95) · language_preserved 1.000 (1.0)
                                                       identifiers_kept 1.000 (1.0) · no_forbidden_content 1.000 (1.0) · rationale_present 1.000 (0.95)
                                                       mode_shape 1.000 (0.95) · overall 1.000 (0.95)
                                                       p95 latency 14 ms (budget 4000) · p95 cost 448 micro-dollars (budget 2000)
                                                       EVALS GREEN
pip-audit / gitleaks / licences                        No known vulnerabilities found · no leaks found · GATE GREEN
selftest                                               45/45 checks red on their plant
VERIFY GREEN
```
```
$ make ci
see the task output pasted below the record when it completes (the same steps in python:3.12.14-slim)
```
Planted regressions (each reverted, each red): a line added to the prompt's system segment →
every fixture missing → `EVALS RED` (a prompt change without a re-recording); a fixture that
drops `PROJ-42` → `identifiers_kept 0.981 < 1.0` → `EVALS RED`; the descriptor's cost budget
lowered under the measured 448 µ$ → `GATE RED at: budgets`.

## Eval and budget numbers
improve-story set v1, prompt v1, `text-default`: **1.000 on every grader; overall 1.000; p95
latency 14 ms; p95 cost 448 µ$** (52 cases). **These numbers measure the pipeline, the scanners,
the graders and the budget accounting over authored, provider-shaped fixtures — no provider key
exists on this machine, so the live model is unmeasured.** The first `make record LIVE=1
CAP=improve-story` with `CATALYST_AI_RECORD_PROVIDER_KEY` replaces the fixtures and these numbers
are re-stated; a `D-NNN` records the switch. Latency excludes provider time for the same reason.

## Decisions and questions
- D-007 proposed: the operation is `POST /v1/improve-story` with operationId `improve_story.run`
  (the repository's `ARCH-004 §2` shape); the planning note that named `/v1/capabilities/improve-story`
  and `capabilities.improveStory` differs from the repository's documentation, and the
  repository's documentation wins.
- D-008 proposed: v1 retires `ai-improve-story`'s rewrite modes only; `ai-improve-comment` stays
  planned under `improve-comment` — a comment polish has its own rules (no headings, no greetings,
  stay close in length, its `suggest_reply` mode is a different capability) and earns its own
  prompt and eval set; folding it into this capability would mean one prompt serving two contracts.
- D-009 proposed: v1 ships on authored fixtures with the limitation stated in the set's README,
  the ledger row and this record; the live recording is the next action once a key exists.
- Q-004: the output language and any product persona are request data, never prompt text — the
  previous system hard-coded English and a tenant's name into the prompt. v1 preserves the input's
  language unless `language` names a target. The product decides the default; the prompt does not.
- F-004: the previous `ai-improve-story` sent attachment URLs and read comments from tables; v1
  carries neither (`Q-003`).

## Commit
Two proposals (generated artefacts on their own, `RULE-005 §2`):
1. Files: `src/**`, `tests/unit/**`, `tests/contract/**`, `tests/architecture/**`, `evals/**`, `tools/**`, `.importlinter`, `Makefile`, `docs/**`, `brain/**`
   Proposed: `feat(improve-story): contract v1, gemini adapter, eval harness, the golden capability`
2. Files: `api/openapi.yaml`, `tests/fixtures/providers/gemini/improve-story/**`
   Proposed: `gen: contract document and authored fixtures for improve-story v1`
Green light: given by the lead on 2026-09-19 — committed on local `main` in the proposed order (no remote yet)

## Next
AI-004 — structured generation (`generate-stories`, `generate-epics`, `suggest-children`) on the
golden shape; and, the moment a provider key exists, `make record LIVE=1 CAP=improve-story` with
the numbers re-stated.
