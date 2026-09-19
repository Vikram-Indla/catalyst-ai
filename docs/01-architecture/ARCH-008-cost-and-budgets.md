---
id: ARCH-008
title: Cost, latency and budgets
status: Locked
version: 1.0.0
owner: AI service lead
created: 2026-09-18
---

# ARCH-008 — Cost, latency and budgets

## 1. Budgets are declared, then tested

Every capability descriptor declares `p95_latency_ms` and `p95_cost_micros` per call. The eval
run measures both over the set; `tools/checks/budgets` fails the gate when a measurement crosses
the declaration. A budget is widened only by a `D-NNN` with the reason; a capability that cannot
meet its budget on the recorded set is not done.

| Family | Default p95 latency | Default p95 cost | Timeout |
| --- | --- | --- | --- |
| Rewrite, translate | 4 000 ms | 2 000 µ$ | 10 s |
| Structured generation | 8 000 ms | 6 000 µ$ | 20 s |
| Summaries | 8 000 ms | 6 000 µ$ | 20 s |
| Retrieval query | 800 ms | 200 µ$ | 5 s |
| Ingest (job) | per document: 30 000 ms | 20 000 µ$ | 120 s per document |
| Assistant (stream) | first frame 1 500 ms; total 15 000 ms | 8 000 µ$ | 30 s |

A descriptor may tighten these; loosening is the `D-NNN` above. The timeout is the adapter's
per-call deadline (`ARCH-005 §2`) and the job model's decision boundary (`ADR-007 §1`).

## 2. Per-tenant budgets, enforced here

`tenant_budgets` counts spend per organisation and per capability in a rolling window; stage 2
of the pipeline (`ARCH-003 §2`) refuses with `ai.budget.exceeded` and `Retry-After` when the
counter would cross the limit from configuration. The service enforces this itself — it does not
assume the backend throttles — because a runaway (a loop, a retry storm, a script) must trip the
tenant's budget before it trips the bill. Limits per organisation come from configuration with a
platform default; an organisation-specific override is a configuration row, never code.

## 3. The cache

A cost tool with a correctness rule. The key is
`sha256(organization_id · capability · capability_version · prompt_version · model alias · canonical(classified input))`;
any component changing invalidates. The value is the validated response model. TTL per
capability from the descriptor. The cache is never shared across organisations — two
organisations sending identical text produce two entries — and `Idempotency-Key` resolves through
the same table, scoped by organisation. Cache hits are logged as such and cost zero.

## 4. What the dashboards show

Spend per organisation, per capability and per model alias; p95 latency per capability; cache
hit ratio; budget refusals per organisation; provider circuit state. Each is a metric from
`platform/observability` (`ARCH-010 §2`); a capability lands with its rows on the dashboard and
an alert threshold at 80% of its declared budget.
