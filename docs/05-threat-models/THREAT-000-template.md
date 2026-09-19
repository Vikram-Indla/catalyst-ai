---
id: THREAT-000
family: <capability family or platform package>
status: Draft | Reviewed
reviewed: YYYY-MM-DD
asvs: 5.0
llm-top10: 2025
---

# THREAT-000 — <family>

## Assets

What an attacker would want here, each with its data class (`ARCH-002 §3`): tenant text in
requests, embeddings and cache values in storage, provider keys, the service token, the eval
sets (synthetic — low), the provider log (content-free — medium).

## Entry points and trust boundaries

Every way in: the operations of the family, the job endpoints, the stream, the worker, the
retention job, the CLI. Where trust changes: token verified, tenant set on the storage session,
input classified and scanned, the completion parsed and scanned.

## Attackers

The backend with a bug (wrong `organization_id`) · a tenant's user through the backend (prompt
injection in a title, a hostile document) · a compromised provider or a provider returning
another caller's text · a compromised service token · a malicious operator with configuration
access · the retention job with a bug.

## Threats

| # | Attacker | Entry point | Attack | Mitigation (code) | Verified by (test / monitor) | ASVS / LLM |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | user via backend | request field | instruction in user text steers the model | delimiting, role separation, output schema (`RULE-008 §2`) | `test_injection_*`, eval `injection` tag | LLM01 |
| 2 | user via backend | request field | secret or personal value in input reaches a provider | input scanner refuses (`ARCH-009 §2`) | safety tests, 100% coverage | LLM02, V5 |
| 3 | provider | completion | foreign identifier, secret pattern, unrequested URL in output | output scanner (`ARCH-009 §3`) | leakage tests | LLM02, LLM05 |
| 4 | backend bug | `organization_id` | cache or index read across tenants | tenant-scoped key and query; RLS | contract tests with two organisations | V4 |
| 5 | user via backend | document | parser bomb, macro, external fetch | limits, subprocess, no fetch (`ARCH-006 §4`) | parser property tests | LLM03, V12 |
| 6 | tenant script | any operation | budget exhaustion, cost runaway | per-tenant budgets and concurrency (`ARCH-008 §2`) | budget tests | LLM10 |
| 7 | operator | configuration | retention enabled at a provider | refused row; `check` fails | `catalyst-ai check` | LLM06 |

## Residual risk

What is accepted, why, who accepted it (`D-NNN`), and the trigger to revisit.
