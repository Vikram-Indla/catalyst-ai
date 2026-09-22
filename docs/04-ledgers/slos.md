# SLOs — what this service promises, and the metric that measures each promise

Every row is a promise the backend may rely on, the metric that measures it, and the alert that
fires when it is at risk. The metrics are the ones the ops port exposes (`ARCH-010 §2`,
`platform/observability/metrics.py`); the alerts live in `ops/alerts.yaml` and each names a
runbook in `docs/06-runbooks/`. Numbers come from `ARCH-008 §1` (the per-capability budgets) and
from what the sets measure today, not from wishes; they move with a `D-` row.

Written by hand. `tools/checks/alerts` fails an alert that names a runbook which does not exist
and an alert this page never names; a runbook that no alert points at is a report, because a
procedure (a rotation, a rebuild, a kill switch) may exist without anything firing.

The histogram's bucket bounds carry an edge at 0.8 s and at 8 s — the two latency objectives —
so the quantiles those rules judge are read at the boundary rather than interpolated across it.

## Service level objectives

| SLO | Objective | Metric | Window | Alert |
| --- | --- | --- | --- | --- |
| Availability of a synchronous capability | 99.0 % of calls answer without `5xx` | `catalyst_ai_http_requests_total{status}` per `operation` | 30 days | `CapabilityErrorBudgetBurn` |
| Latency of a generation capability | p95 within the capability's budget (`ARCH-008 §1`: 8 s) | `catalyst_ai_http_request_duration_seconds` per `operation` | 1 hour | `CapabilityLatencyHigh` |
| Latency of retrieval | p95 within 800 ms (`ARCH-008 §1`); its own threshold, because one number cannot serve two budgets | `catalyst_ai_http_request_duration_seconds{operation=~"search.*"}` | 1 hour | `RetrievalLatencyHigh` |
| Latency of the provider | p95 provider call within the same budget; a slow provider is not a slow capability twice | `catalyst_ai_provider_call_duration_seconds` per `capability`, `model` | 1 hour | `ProviderLatencyHigh` |
| Provider availability | fewer than 5 % of provider calls end in `ai.provider.unavailable`, `timeout` or `quota` | `catalyst_ai_provider_calls_total{outcome}` | 1 hour | `ProviderFailing` |
| Grounding refusals | fewer than 1 % of answers are refused as `ai.output.invalid` — above that the prompt or the model moved | `catalyst_ai_errors_total{code}` | 6 hours | `OutputRefusalsHigh` |
| Tenant budget | an organisation's daily spend stays under its cap; a tenant at the cap is refused, never served slowly | `catalyst_ai_provider_cost_micros_total{organization}` and `catalyst_ai_errors_total{code="ai.budget.exceeded"}` | 1 day | `TenantBudgetExhausted` |
| Cache | at least 20 % of eligible calls are served from the cache; a collapse means the key moved | `catalyst_ai_cache_lookups_total{result}` | 6 hours | `CacheHitRateLow` |
| Job queue | a job starts within its window; fewer than 1 % expire unstarted | `catalyst_ai_jobs{state="queued"}`, `catalyst_ai_jobs{state="running"}` | 1 hour | `JobQueueBacklog` |
| Proof of origin | every refusal is a caller defect, never a forged envelope: `bad_signature` at zero | `catalyst_ai_origin_refused_total{reason}` | 1 hour | `OriginForged`, `OriginRefusalsHigh` |
| Request accounting | the request total counts served operations only; probes and scrapes are on the ops port and counted nowhere | `catalyst_ai_http_requests_total{operation!="unknown"}` | — | the denominator of the rules above |
| Job integrity | no job row fails its stored proof: `job_quarantined` at zero | `catalyst_ai_job_quarantined_total{reason}` | 1 hour | `JobQuarantined` |
| Retrieval index | the index answers; `ai.index.unavailable` is zero outside a rebuild | `catalyst_ai_errors_total{code="ai.index.unavailable"}` | 1 hour | `IndexUnavailable` |
| The door's store | the replay store answers, so the door decides rather than fails closed | `catalyst_ai_errors_total{code="auth.origin.unverifiable"}` | 1 hour | `OriginUnverifiable` |
| Readiness | the process reports `not_ready` only while draining | `/readyz` (the probe, not a metric) | — | the orchestrator's own probe |

A capability turned off on purpose (`docs/06-runbooks/kill-switch.md`) is not a breach of any
objective above and raises no alert of its own: the calls it would have served are refused with
`ai.capability.disabled`, which the backend expects and shows as unavailable.

## What is deliberately not measured

- **Content.** No metric carries a prompt, a completion, a title or a member's text; the label
  vocabulary is capability, model, outcome, reason, status class, organisation id and job state
  (`ARCH-010 §1`, `tools/checks/logs`).
- **Quality.** Eval scores are not metrics: they are the gate's floors, measured per change on
  authored or recorded sets, not per minute in production. A model that gets worse shows here as
  refusals (`ai.output.invalid`) and in the next eval run — that is the design (`ADR-005`).
- **Per-organisation latency.** Cardinality: the organisation label is carried only on cost,
  where the budget needs it. A tenant's latency is read from its capability's series.

## Reading a burn

An error-budget burn alert says the objective will be missed if the rate continues, not that it
has been missed. The runbook's first three commands are always: the alert's own metric by label,
the same window for the neighbouring capabilities, and the provider's outcomes — a burn that is
only in one capability is that capability's; a burn in all of them is the provider's or the
database's.
