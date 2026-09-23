# Provider outage — `ProviderFailing`: the breaker is open, calls time out, or the quota is spent

**Alerts:** `ProviderFailing`, `ProviderLatencyHigh`.

## What the backend sees

Every provider failure is already a catalog error on its side: `ai.provider.unavailable` (503,
retryable), `ai.provider.timeout` (504), `ai.provider.quota` (429 with `Retry-After`),
`ai.provider.rejected` (422 — the model refused the input, not an outage). No capability serves a
degraded answer instead: a failed call is a refusal, by design.

## The first three commands

1. `sum by (outcome) (rate(catalyst_ai_provider_calls_total[15m]))` — which outcome dominates.
   `unavailable` and `timeout` are the provider or the network; `quota` is the account; `rejected`
   is the input and belongs to the capability, not here.
2. `histogram_quantile(0.95, sum by (capability, le) (rate(catalyst_ai_provider_call_duration_seconds_bucket[15m])))`
   — a latency rise before the failures means the provider is degrading, not down.
3. The provider's own status page, and `catalyst_ai_errors_total{code=~"ai.provider.*"}` by code
   for what the backend is actually receiving.

## What the service does by itself

Bounded retries with jitter, then a circuit breaker per model: after a run of failures the
breaker opens and calls fail fast with `ai.provider.unavailable` until a probe succeeds. This is
why a provider outage does not become a thread pile-up. Nothing to turn on.

## When to disable a capability

When the provider is up but one capability's calls are failing (`rejected` on most calls, or a
model that was swapped under us): disable that capability with its kill switch
(`docs/06-runbooks/kill-switch.md`) so the backend gets a clean `ai.capability.disabled` instead
of a slow refusal, and say so in the incident.

## `ProviderLatencyHigh` — the provider answers, past the capability's budget

Each capability's provider calls are judged at the p95 its descriptor declares (`ARCH-008 §1`;
`tools/checks/latency` keeps the rule and the descriptor equal): 800 ms for the search
embedding, 4 s for `improve-story`, 15 s for `documents`. A ticket, not a page — the calls
still succeed. Read it beside `CapabilityLatencyHigh`: both firing for the same capability is
the provider; `CapabilityLatencyHigh` alone is time spent inside the service (retrieval, a
parser child, the cache). Command 2 above by `model` says whether one model is slow or all are.
If one model stays slow for a day, that is the register's question (a `D-` row and an eval run),
never a hot edit of the alias.

## When to page

`ProviderFailing` for more than ten minutes across every model, or a quota exhaustion in
production — both mean no assisted feature works. A single model failing is a ticket: the
register names the alias, and a model swap is a `D-` row plus an eval run, never a hot edit.
