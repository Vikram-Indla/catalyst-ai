# 018 — alerts that can actually fire, and the model an environment runs

**Date:** 2026-09-26 · **Ticket:** AI-014 (follow-up) · **Capability or package:** platform/observability (the ops app, the worker's registry, the gauges), ops/alerts.yaml, two runbooks, tools/checks/alerts, config + providers (the alias knob) · **Author:** a contributor

## Read
A reviewer's line-by-line audit of what session 017 shipped — every label in `ops/alerts.yaml`
checked against the code that writes it — and the lead's request for a model selectable per
environment. Then the code the audit named: `cli.py`'s two app builders, `app.py`'s middleware
order, `SecurityCounters.__init__`, `scrape.read_gauges`, `BUCKETS_S` against the SLO ledger's
own thresholds, `providers/gemini/aliases.py` and the register's rows.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-014 (follow-up)
Capability or package: platform/observability — a dedicated ops app, the worker's registry, the queue gauges, bucket bounds;
                 ops/alerts.yaml — seven rules changed, one added; tools/checks/alerts — the orphan rule becomes a report;
                 docs/06-runbooks — origin-refusals.md, replay-store-down.md (new); config + contract/models + providers/gemini/aliases —
                 the alias an environment selects; Makefile — the drills join the gate
Inputs:          none new
Tenant boundary: unchanged
Provider/model:  the model a capability runs is now selectable per environment and per capability, by alias
Prompt version:  unchanged
Eval set:        unchanged — and deliberately so: the code default stays the row the floors were measured on
Budget:          unchanged; a deployment that selects `text-fast` runs a cheaper row knowingly
Failure mode:    a page-severity alert over a series that can never move → the worker counts into the process's registry;
                 a scrape a collector cannot reach → the ops port is its own app with no door in front of it
Cache:           unchanged
Safety:          unchanged; the ops port still carries no content and now carries no capability either
Contract:        unchanged on the wire; one configuration variable replaced (`MODEL_TEXT_DEFAULT` → `MODEL_TEXT_ALIAS`)
Invariants:      INV-059, INV-060 (new)
Blast radius:    SYSTEM — the ops surface, the composition root, the model every capability resolves
Decision level:  2
ADR:             none; ARCH-005 1.1.0 (configuration names an alias); D-040
```

## Changed
- **The worker counted into a private registry (F-033).** `cli.py` built the `Worker` with a
  bare `SecurityCounters()`, which made itself a fresh `Metrics()`; the ops app beside it
  rendered the process's. So `job_quarantined{reason}` — the page-severity rule of the whole
  service — landed in an object nothing scrapes. `SecurityCounters` now requires the registry
  (no bare default), the worker is given the process's, and a contract test quarantines a row on
  the real loop and then asserts the counter in the scrape's own text.
- **The scrape sat behind the door, and the probes were counted as traffic (F-032).** The ops
  port was built by `create_app`, so the proof of origin stood in front of `/metrics` — which a
  collector can never satisfy — and every probe and scrape incremented the shared request
  counter under `operation="unknown"`, putting thousands of synthetic requests a day into
  `OutputRefusalsHigh`'s denominator. There is now `create_ops_app`: liveness, readiness and the
  scrape, sharing the runtime and the registry, with no door and no request metrics. Three tests,
  including one that calls `/metrics` on the contract app and asserts it is refused.
- **The queue gauges froze into a lie.** `read_gauges` returned on a storage outage leaving the
  last depth rendered as if current; it drops the series now, so `JobQueueBacklog` sees absence
  rather than a stale number (F-030's family again).
- **One latency threshold served two budgets.** `CapabilityLatencyHigh` judged everything at 8 s
  while `ARCH-008 §1` gives retrieval 800 ms, so a search at 7.9 s was silent. Retrieval has its
  own rule now, and `BUCKETS_S` carries an edge at **0.8** and at **8.0**: a quantile
  interpolated across the threshold it is judged by measures nothing.
- **`TenantBudgetExhausted` promised a tenant its series cannot name** (the error counter carries
  the code alone, by the cardinality decision) and `increase(…[1d]) > 0` kept it firing for a day
  after one refusal. It is a rate over an hour now, and its summary names the metric that *does*
  carry the organisation.
- **Two alerts pointed at runbooks about something else** — and my own check pushed them there:
  `coverage_violations` failed the gate for any runbook no alert names, so the last two alerts
  were spent satisfying the check. That half is a **report** now; the direction worth failing
  over (no alert without a runbook that exists, no alert the SLO ledger never names) is
  unchanged. The door got the two pages it actually needs: `origin-refusals.md` (the reason
  table for every refusal the door counts) and `replay-store-down.md`.
- Smaller, from the same review: `JobQueueBacklog` aggregates with `max by (state)` so one queue
  pages once rather than once per replica; `CacheHitRateLow` gained a floor under its
  denominator; the `health` router is no longer included twice; **the drills run in `make verify`**
  (`make drills`) — a kill switch that is never exercised is the one that fails.
- **The model an environment runs (the lead's request, D-040).** `MODEL_TEXT_ALIAS` selects a
  register row — `text-default`, `text-fast`, `text-long` — globally, and
  `CAPABILITY_<NAME>_MODEL_ALIAS` lifts one capability above it. The value is an **alias**: the
  vocabulary moved to `contract/models.py` so the settings can validate against it, an unknown
  value fails at settings load, and no environment can reach a model the register has not priced.
  `.env.example` carries `text-fast`, the cheapest row, with the reason written next to it.

## Verify
```
$ make verify
GATE GREEN (47 checks) · oasdiff: no breaking change against main · 805 passed · coverage 99 % · storage green · the two drills green inside the gate · fourteen sets EVALS GREEN · pip-audit: no known vulnerabilities · selftest: 49/49 checks red on their plant
VERIFY GREEN
```
```
$ make ci
GATE GREEN (47 checks) · 805 passed · coverage 99 % · EVALS GREEN · selftest: 49/49
VERIFY GREEN
stamp: tree 76cb852292dc in python:3.12.14-slim at 2026-09-22T16:55:07+00:00 -- green
(the first attempt died in the container's package step — `apt-get` lost DNS mid-download and
the gate never ran; the retry is the run above. The pipeline installs `make`, `git` and `curl`
on every run, so a network blip is a red gate that says nothing about the tree — the reviewer's
standing point, and item 4 of the proposal with the product owner.)
```

## Eval and budget numbers
Unchanged, and that is a decision rather than an accident: **the code default stays
`text-default`**. A fixture is keyed by the request and the model id is in the URL, so moving the
default to the cheaper row would invalidate every recorded fixture and every floor measured on
them — it would not save money, it would delete the evidence. `.env.example` selects `text-fast`
so a deployment runs the cheap row knowingly, and the config ledger says in the same sentence
that the floors were measured on the other one. The grader is not selectable at all: it is the
measuring instrument, not the product.

## Decisions and questions
- D-040 (configuration names an alias, never a model id; the default is what was measured).
- F-032 (the ops port), F-033 (the worker's registry) — both are the same class as F-031 from the
  previous session: a number that cannot move, in a place nobody looks until the night it matters.
  Three findings of that shape in two sessions is the argument for the reviewer's habit of
  checking that every label in an alert exists in the code that writes it.
- Stated plainly: the reviewer also asked for the **restart-to-refusal time** in the drill
  transcript, since that is the rollback time of the only lever an operator has. The drill
  measures a process that is already up, so the honest number is not the drill's to give — it is
  the deployment's restart time plus the process's own start-up, and it belongs in the runbook
  once a deployment exists. `kill-switch.md` says the mechanism is a restart; it does not yet
  promise a number, and I would rather it stayed silent than guessed.

## Commit
1. Files: `src/**`, `tools/**`, `tests/**`, `ops/**`, `docs/**`, `brain/**`, `Makefile`, `.env.example`
   Proposed: `fix(observability): alerts that can fire, a scrape a collector can reach`
Green light: given

## Next
The reviewer's acknowledgement; the live recording on the authored sets (the key exists, free
tier — the record will say so); the pipeline's own findings if the product owner cuts them.
