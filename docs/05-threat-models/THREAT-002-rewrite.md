---
id: THREAT-002
family: rewrite (improve-story; later improve-comment, translate-field)
status: Draft
reviewed: —
asvs: 5.0
llm-top10: 2025
---

# THREAT-002 — rewrite

## Assets

The member's text in the request (`CONFIDENTIAL`); the cached proposals in `cache_entries`
(`CONFIDENTIAL`, per tenant); the provider key (`RESTRICTED`, configuration only); the service
token (`RESTRICTED`); the prompt file (`INTERNAL` — its leak reveals nothing about a tenant but
helps an attacker craft injections); the provider-call rows (content-free, `INTERNAL`).

## Entry points and trust boundaries

`POST /v1/improve-story` (the only operation). Trust changes at: the service token
(`ServiceTokenMiddleware`); the request model (FastAPI validation, `extra="forbid"`, sizes); the
door (`validate`: switch, contract version, scanner, tenant cap); the fences around every user
field in assembly; the schema and the leakage scanner on the completion; the cache key.

## Attackers

A member through the backend (prompt injection in any text field, a hint that redirects the
task, a request to reveal the prompt) · the backend with a bug (a wrong `organization_id`, a
`RESTRICTED` value in a text field) · the provider (a blocked or garbage completion; a
completion carrying another caller's text) · a tenant script (budget exhaustion) · a compromised
service token · an operator with configuration access.

## Threats

| # | Attacker | Entry point | Attack | Mitigation (code) | Verified by (test / monitor) | ASVS / LLM |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | member | `description`, `focus_hint`, any text field | instruction in the data steers the model or changes the output shape | fences (`platform/safety/delimit`), role separation, the system segment's data rule, the output schema (`ModelOutput`, `extra="forbid"`) | `test_assembly_fences_every_user_field_and_names_the_mode`; eval cases `injection-01..06`; `no_forbidden_content` floor 1.0 | LLM01, V5.1 |
| 2 | member | any text field | closes a fence to inject a segment | `strip_markers` on every user field before fencing | `test_fence_wraps_and_strips`; eval `injection-02` | LLM01 |
| 3 | member | any text field | asks the model to reveal or repeat its instructions | the refusal rule in the system segment; the output scanner refuses an echoed fence | `test_fence_echo_refused`; eval `injection-01`, `injection-03` | LLM07 |
| 4 | backend bug | any text field | a `RESTRICTED` value (email, key, IP) reaches the provider | the input scanner refuses with a reason class, never the value | `test_restricted_patterns_refused` (7 patterns); `test_improve_story_run_input_rejected_and_too_large` | LLM02, V8 |
| 5 | provider | the completion | a foreign item key, a link, a secret, a fence in the completion | the output scanner → `ai.output.unsafe`, a content-free security event | `test_output.py`; `test_leaking_output_is_refused`; eval `injection-04`, `leakage-01/02` | LLM02, LLM05 |
| 6 | provider | the completion | schema-invalid text | one repair call, then `ai.output.invalid`; nothing partial returned | `test_invalid_output_is_repaired_once_then_refused` | LLM05 |
| 7 | backend bug | `organization_id` | a cache hit across organisations | the key carries the organisation; idempotency keys are organisation-scoped | `test_cache_hits_are_free_and_never_cross_organisations`; contract test with two organisations | V4.2 |
| 8 | tenant script | the operation | spend or concurrency runaway | `TenantBudgets.reserve` before the call, `slot` around it; `ai.budget.exceeded` with `Retry-After` | `test_tenant.py`; `test_budget_exceeded_refused_before_any_call` | LLM10 |
| 9 | anyone | the operation | a call without the service token | constant-time compare; 401 before routing | `test_improve_story_run_requires_the_service_token` | V2.2 |
| 10 | operator | configuration | the capability misbehaves in production | the kill switch returns `ai.capability.disabled` before any call | `test_kill_switch_refuses_before_any_call` | — |
| 11 | provider | the wire | an outage or a slow provider holds threads | per-call deadline, bounded retries with jitter, a breaker per model | `test_adapter.py` (retry, breaker, timeout) | V12 |
| 12 | anyone | logs | content in a log line | the row model has no content field; the redacting filter; `tools/checks/logs` | `test_row_has_no_content_field`; the gate | LLM02 |

## Residual risk

- The scanners are pattern-based: a `RESTRICTED` value that matches no pattern (a name without an
  email, a phone number) passes the door. Accepted for v1 because the backend's classification is
  the first line and the contract has no `RESTRICTED` field; revisit when the backend's
  personal-data classification ships (`Q-001`).
- v1's fixtures are authored: the injection cases prove the pipeline and the scanners, not the
  live model's behaviour under attack. Revisit at the first live recording; the eval numbers are
  re-stated then.
- Accepted by: pending the lead (`D-NNN`).
