---
id: THREAT-003
family: structured generation (generate-children; later generate-workflow, generate-test-cases)
status: Draft
reviewed: —
asvs: 5.0
llm-top10: 2025
---

# THREAT-003 — structured generation

## Assets

The parent's text, the attached source texts and the sibling titles in the request
(`CONFIDENTIAL`); the organisation's hierarchy and level names (`INTERNAL`); the cached candidate
lists (`CONFIDENTIAL`, per tenant); the provider key and the service token (`RESTRICTED`); the
prompt file (`INTERNAL`).

## Entry points and trust boundaries

`POST /v1/generate-children`. Trust changes at the service token; the request model (sizes,
`extra="forbid"`, at most 10 sources and 100 siblings); the door (switch, version, **the hierarchy
check on the request**, scanner, tenant cap); the fences around every user field including the
joined sibling and source lists; the schema, **the hierarchy check on the output**, the leakage
scanner; de-duplication and bounding; the cache key.

## Attackers

A member through the backend (an instruction in the parent text, in a sibling title, in a source
document, in the hint) · the backend with a bug (a hierarchy that skips levels, a wrong
`organization_id`) · the provider (candidates at the wrong level, invented identifiers, a candidate
naming another tenant's item) · a tenant script (many sources, many siblings, max items) · the
member who wants the service to *create* items (it never does).

## Threats

| # | Attacker | Entry point | Attack | Mitigation (code) | Verified by | ASVS / LLM |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | member | any text field, a sibling title, a source | instruction steers the model or changes candidate types | fences with marker stripping; the data rule in the system segment; the output schema; the hierarchy check refuses any wrong level | eval `*-injection-01..04`; `test_wrong_level_output_is_output_invalid_with_hierarchy_violation` | LLM01 |
| 2 | provider | the completion | a candidate at the parent's level or two levels down | `check_hierarchy` → `ai.output.invalid` with `hierarchy_violation`; nothing partial returned | unit and contract tests on scripted outputs; `level_correct` floor 1.0 | LLM05 |
| 3 | backend bug | `child_level`, `parent_level` | a request asking for a level that is not the parent's next | `expected_child_level` at the door → `ai.input.rejected` with `hierarchy_violation`, before any call | `test_skipping_a_level_is_refused_at_the_door_before_any_call` | V5 |
| 4 | provider | the completion | invented keys, numbers or links | the leakage scanner (foreign keys, unrequested links, secrets); `identifiers_kept` grader floor 1.0 | `test_leaking_candidate_is_refused`; eval `*-identifiers-01`, `*-leakage-01` | LLM02, LLM05 |
| 5 | provider | the completion | repeats of existing siblings presented as new work | lexical de-duplication marks `duplicate_of`; duplicates do not count against `max_items` | `test_mark_duplicates_against_siblings_and_earlier_candidates`; `duplicates_marked` floor 1.0 | — |
| 6 | tenant script | sources, siblings, `max_items` | cost runaway | request bounds (10 sources, 100 siblings, 20 items), total-size door, per-tenant spend and concurrency caps, `max_output_tokens` from the descriptor | contract tests `too_large`, `budget_exceeded` | LLM10 |
| 7 | backend bug | `organization_id` | a cache hit across organisations | the key carries the organisation | contract test with two organisations | V4.2 |
| 8 | member | any | the service creates items | there is no write path: the response is candidates, the backend owns creation (`ARCH-002 §2`) | the boundary tests; the contract carries no create operation | — |
| 9 | anyone | logs | candidate text in a log line | the row model has no content field; `tools/checks/logs` | `test_row_has_no_content_field`; the gate | LLM02 |

## Residual risk

- De-duplication is lexical (prefix-stemmed token overlap, threshold 0.6): a paraphrase with
  different words passes as new. Accepted for v1; the retrieval-backed similarity replaces the
  same function when the embeddings package lands.
- v1's fixtures are authored: the injection cases prove the fences, the hierarchy check and the
  scanners, not the live model's behaviour. Revisit at the first live recording.
- Accepted by: pending the lead (`D-NNN`).
