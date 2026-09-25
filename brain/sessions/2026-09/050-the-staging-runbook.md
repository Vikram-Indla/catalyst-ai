# 050 — The staging runbook

**Date:** 2026-09-24 · **Ticket:** AI-036 (the runbook) · **Capability or package:** `docs/06-runbooks/staging.md` (new), the runbook index, `F-046` · **Author:** a contributor

The service is releasable to staging (records 044–049). Whoever promotes it needs one page:
- how it starts, and how it stops;
- the capabilities switch and how to flip it;
- rollback;
- where the logs are, and which alerts exist;
- what "a deployed process refuses to start" means and what to do.

The page follows the shape of the other runbooks. It marks every step that follows the product
documentation but has not been run here.

## Read
The runbooks and their index; `ops/alerts.yaml` and `tools/checks/alerts`; the start refusals in
`config/deployed.py`, `config/residency.py`, `config/logins.py`; `catalyst-ai check`; the log
formatter; records 044–049.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-036 (the runbook)
Capability:      none
Inputs:          none
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged
Budget:          unchanged
Failure mode:    none
Cache:           none
Safety:          none
Contract:        unchanged
Invariants:      unchanged
Blast radius:    LOCAL — a runbook and a finding
Decision level:  0
ADR:             none
```

## What changed
- **`docs/06-runbooks/staging.md`**:
  - what runs where (service, worker pool, job; each with the login it reads);
  - start: a release, the migration's promoted first;
  - stop: capabilities off, or the invoker grant withdrawn; the worker pool to zero **(verify)**;
  - the capabilities switch: the durable way (the target's parameter, a new release) and at once
    (`gcloud run services update … --update-env-vars`, **verify**);
  - rollback: re-promote the previous release; migrations forward-only;
  - logs: JSON lines filtered by `request_id`, with the severity field **to verify**;
  - alerts: the fourteen rules, none of which can fire on staging yet;
  - the refusal table, with each message as the service prints it and its cause and fix.
- The index gains the page.
- **`F-046`** (open): the alert rules read `/metrics` on the ops port, which Cloud Run does not
  expose, and nothing exports a metric elsewhere (`OTEL_EXPORTER_ENDPOINT` is a setting with no
  exporter behind it). On staging no alert can fire until the planned alert work.

## Checked while writing (two claims corrected before they went in)
- An unknown `CATALYST_AI_…` variable does **not** refuse the start: `catalyst-ai check` passes with
  one set, so the setting silently keeps its default. The page says so instead of listing it as a
  refusal, and points to the deployment check, which refuses unknown names in `deploy/`.
- Under `F-045`:
  - the API refuses with `DATABASE_WORKER_URL and DATABASE_MIGRATE_URL are required outside
    development`;
  - the worker and the migration refuse earlier, with `database_url  Field required`, because
    serve's URL is a required field for every process.

  Both were checked with `catalyst-ai check` under the worker's settings; the page and `F-045` name
  both messages.

## Eval and budget numbers
No capability changed; no eval set moved.

## Verify
Fast checks in the loop: the static gate (the alerts check reads the runbook directory; the new
page is reported as having no alert point at it, which is allowed). The full gate runs before this
is pushed; its output is pasted here then.

The full gate on the tree this change is committed from:
```
$ make verify
VERIFY GREEN — GATE GREEN (56 checks) · 1189 passed, coverage 99.41% · EVALS GREEN · selftest 58/58 (on the host, before record 043's make hooks fix)
$ make ci
VERIFY GREEN in catalyst-ai-ci:d06a9811d6b3 — 56 checks · 1189 passed, 99.41% · EVALS GREEN · selftest 58/58 · stamp: tree f777f5806cb3 at 2026-09-25T07:16:19+00:00 -- green
```

## Decisions and questions
- `F-046` opened.

## Commit
- `docs(runbooks): staging — start, stop, the switch, rollback, logs, refusals`
