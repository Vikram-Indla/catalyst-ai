# 017 — operational readiness: the numbers, the alerts, the drills, the drain

**Date:** 2026-09-26 · **Ticket:** AI-014 · **Capability or package:** platform/observability (metrics, the scrape, the metered port, request metrics), the SLO ledger, the alerts and dashboard, four runbooks, the drill and load harnesses, the API's drain · **Author:** a contributor

## Read
`ARCH-010` (every call a row, the ops port's metric list, logs without content, runbooks per
capability), `ARCH-008 §1` (the budgets the latency objectives come from), `ADR-005` (why eval
scores are gate evidence and not production metrics), the door and the job gate's counters from
the two previous records, the storage adapter's sessions, `uvicorn`'s graceful shutdown, and the
reviewer's standard for alerts (an alert names a runbook; a runbook opens with the first three
commands and says when to page).

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-014
Capability or package: platform/observability — metrics.py (the registry), scrape.py (`/metrics` on the ops port),
                 requests.py (RED middleware), provider.py (the metered port), security.py (now backed by the registry);
                 platform/runtime (the registry is a seam of the process); platform/pipeline (cache lookups);
                 platform/httpserver (errors counted where they are rendered, and where a stream ends);
                 cli (the API drains on SIGTERM); tools/drill.py, tools/load.py, tools/checks/alerts.py,
                 tools/checks/origin.py (the secret-path rule); docs/04-ledgers/slos.md; ops/alerts.yaml, ops/dashboards/service.json
Inputs:          none new; the scrape is read-only and carries no content
Tenant boundary: unchanged; the organisation id appears on one metric (cost), where the budget needs it
Provider/model:  unchanged — the adapter is wrapped, not altered
Prompt version:  unchanged
Eval set:        unchanged (fourteen sets)
Budget:          unchanged; the spend is now visible per organisation and per capability
Failure mode:    an outage nobody sees → every SLO has a metric and an alert, every alert a runbook;
                 a scrape that fails when the database is down → the gauges are skipped, the scrape still answers
Cache:           unchanged; hits and misses are counted
Safety:          no metric, label or dashboard field carries content; the secret-path rule keeps each secret to one reader
Contract:        unchanged — `/metrics` is on the ops port and out of the contract document
Invariants:      INV-057, INV-058 (new)
Blast radius:    SYSTEM — a new port surface (ops), the composition root, the shutdown path
Decision level:  2
ADR:             none; ARCH-011 names `ops/` (1.0.1); D-038 (the kill switch is restart-based), D-039 (the exposition format)
```

## Changed
- `platform/observability/metrics.py` — the registry: counters, gauges, histograms with fixed
  bounds, and `render()` in the Prometheus text exposition format. A read never creates a series.
- `scrape.py` — `GET /metrics` on the **ops port only**, with the queue depth read at scrape
  time; a database that does not answer costs the gauges, never the scrape.
- `requests.py` — one count per operation and status class, one duration per operation.
- `provider.py` — `MeteredProvider` wraps the port at the composition root: calls, tokens, cost
  and latency by capability, model and outcome, for generation, streaming and embedding. No
  capability can forget to report, because none of them reports.
- `security.py` — the security counters are now a view of the same registry, so
  `origin_refused{reason}` and `job_quarantined{reason}` are scraped like everything else.
- `platform/pipeline/stages.py` — cache hits and misses; `httpserver/rendering.py` — every
  refusal counted by code where it becomes a response; `httpserver/sse.py` — a stream's terminal
  `error` frame counted the same way (it never passed through the renderer, so it was invisible).
- `platform/runtime` — the registry is a field of the runtime, so one process has one registry.
- `cli.py` — the API installs a SIGTERM handler: `/readyz` turns false, uvicorn drains in-flight
  requests inside `SHUTDOWN_DRAIN_SECONDS`, then both servers stop (the worker already did this).
- `docs/04-ledgers/slos.md` — eleven objectives, each with its metric, window and alert, plus
  what is deliberately not measured (content, quality, per-tenant latency) and why.
- `ops/alerts.yaml` — thirteen rules in Prometheus rule format; `ops/dashboards/service.json` —
  a Grafana dashboard: calls, refusals, latency, provider outcomes, tokens, spend per
  organisation, cache hit rate, the queue, the security counters.
- `tools/checks/alerts.py` (+ its in-memory plant) — an alert without a runbook, an alert naming
  a runbook that does not exist, an alert no SLO row mentions, or a runbook no alert points at,
  all fail the gate.
- `tools/checks/origin.py` — the secret-path rule: each secret is read by one module
  (`provider_gemini_api_key` by the Gemini adapter, `database_url` by `app.py` and `cli.py`),
  red on its plant.
- `tools/drill.py` (`make drill CAP=`) and `tools/load.py` (`make load`) — below.
- Runbooks: `provider-outage.md`, `eval-drift.md`, `budget-exhaustion.md`, `kill-switch.md`
  (the last with the degradation table per capability).

## Verify
```
$ make verify
GATE GREEN (47 checks) · oasdiff: no breaking change against main · 802 passed in 207 s · coverage 99 % · storage green · fourteen sets EVALS GREEN · pip-audit: no known vulnerabilities · selftest: 49/49 checks red on their plant
VERIFY GREEN
(the first run was red at one test: `/readyz` now reports `serving` as well, which its assertion predated)
```
```
$ make ci
GATE GREEN (47 checks) · 802 passed · coverage 99 % · EVALS GREEN · selftest: 49/49
VERIFY GREEN
stamp: tree 228b9d0df7ad in python:3.12.14-slim at 2026-09-22T12:30:58+00:00 -- green
(this block was written after the stamp; the push's own run re-proves the tree)
```

### The kill-switch drills
```
drill summarize: switch off -> 503 ai.capability.disabled
  ai.capability.disabled counted: 1; provider calls: 0
drill summarize: switch on  -> 200 served
  ai.capability.disabled counted: 0; provider calls: 1
drill translate while summarize is off -> 200 served
drill: the switch works

drill translate: switch off -> 503 ai.capability.disabled
  ai.capability.disabled counted: 1; provider calls: 0
drill translate: switch on  -> 200 served
  ai.capability.disabled counted: 0; provider calls: 1
drill summarize while translate is off -> 200 served
drill: the switch works

drill improve-story: switch off -> 503 ai.capability.disabled
  ai.capability.disabled counted: 1; provider calls: 0
drill improve-story: switch on  -> 200 served
  ai.capability.disabled counted: 0; provider calls: 1
drill translate while improve-story is off -> 200 served
drill: the switch works
```

### The load run on the streaming path
```
load 16x4: 64 streams, terminals {'done': 64}
  p50 321 ms · p95 419 ms · max 460 ms · provider calls 128 · budget refusals 0
load spent tenant: 16 streams, terminals {'error': 16}
  p50 124 ms · p95 151 ms · max 154 ms · provider calls 0 · budget refusals 16
load: every stream terminated and a spent tenant was refused
```
Sixty-four concurrent streamed turns through the real app over the recorded event streams: every
one ended with exactly one terminal frame, p95 419 ms for the whole turn including the
embedding call; a tenant with no budget left had all sixteen of its streams refused with a
terminal `error` frame before any provider call, and the refusal counter moved by sixteen.

## Eval and budget numbers
No prompt, pipeline or set moved; the fourteen sets re-run unchanged in `make verify` and no
budget line moves. The load numbers above are transport latency over fixtures, not model
latency: they measure this service's own overhead under concurrency, which is what it owns.

## Decisions and questions
- **D-038 — the kill switch is restart-based, and that is the documented mechanism.** A runtime
  config reload is not in the constitution; a watch thread for a knob turned once a quarter buys
  less than it costs. `kill-switch.md` says so plainly and the drill proves the switch.
- **D-039 — the ops port exposes the Prometheus text exposition format.** It is what every
  collector scrapes, including the OpenTelemetry collector, so the collector stays the only
  exporter (`ARCH-010 §2`) and no vendor SDK enters the register; alerts are that format's rule
  files and the dashboard is Grafana JSON, because those are the artefacts a stack imports.
- `ops/` is a new home, so `ARCH-011`'s tree names it (1.0.1) — a law page edit beyond the
  card's allowance, one line, said here.
- Stated plainly: (1) **cache lookups are counted globally, not per capability** — `Stages` has
  no capability name and threading one through twelve pipelines for a label is not worth it;
  the hit-rate SLO is a service-wide number. (2) **The breaker's state is not a gauge**: the
  breaker lives inside the adapter and the metered wrapper cannot see it; `ProviderFailing`
  covers the symptom and the gauge waits for a reason to exist. (3) The load harness drives one
  organisation because the fixture is keyed by the request — it proves the process under
  concurrency and the budget refusal, not many tenants at once. (4) The drill runs in process
  over the recorded fixtures rather than against the compose stack: same app, same door, no
  Docker in the loop, and it can run in the gate; the compose stack adds the network, not the
  behaviour. (5) One bug found by writing this: `Metrics.value` on an unseen series used to
  create it, so an absent gauge rendered as a zero line — reads no longer mutate the registry.

## Commit
1. Files: `src/**`, `tools/**`, `tests/**`, `ops/**`, `docs/**`, `brain/**`, `Makefile`
   Proposed: `feat(observability): the metrics the ops port serves, alerts, drills and drain`
Green light: awaited

## Next
The lead's review; the live recording when the key arrives (AI-013); the ledger reconciliation
the product owner cut after it.
