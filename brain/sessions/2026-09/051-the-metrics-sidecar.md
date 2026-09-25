# 051 — The metrics reach Cloud Monitoring through a sidecar, so the alerts can fire on staging

**Date:** 2026-09-24 · **Ticket:** AI-039 (F-046) · **Capability or package:** `deploy/run/api.yaml`, `deploy/run/worker.yaml`, `deploy/monitoring/run-gmp.yaml` (new), `tools/checks/deployment.py`, the Makefile (`alert-policies`), the staging runbook, `F-046` · **Author:** a contributor

`F-046`: the alert rules read `/metrics` on the ops port, Cloud Run exposes one port, and nothing
exported the numbers. The documented Cloud Run way for Prometheus metrics is the Managed Service
for Prometheus sidecar. This change adds it to the manifests and prints the command that turns the
existing rules into Cloud Monitoring policies. Nothing is deployed.

## Read
Checked on 2026-09-24:
- *Use the Prometheus sidecar for Cloud Run* — **verified**:
  - the sidecar is "the Google-recommended way to get Prometheus-style monitoring for Cloud Run
    services";
  - the example service carries `run.googleapis.com/container-dependencies: '{"collector":["app"]}'`,
    `run.googleapis.com/execution-environment: gen2` and `run.googleapis.com/cpu-throttling: 'false'`,
    with the image `…/cloud-run-gmp-sidecar/cloud-run-gmp-sidecar:1.2.0`;
  - the default scrape is port 8080 `/metrics`; a custom `RunMonitoring` comes from a Secret Manager
    secret mounted at `/etc/rungmp/` (the volume and mount copied verbatim);
  - "When querying the metric with PromQL, you can use the Prometheus name";
  - the sidecar adds the resource labels `project_id`, `location`, `cluster`, `namespace`, `job`,
    `instance`, and the metric labels `instanceId`, `service_name`, `revision_name`,
    `configuration_name`.
- The same page's example service also carries `run.googleapis.com/launch-stage: ALPHA`. Whether that
  is still required is **unverified**; it is not copied.
- Worker pools and jobs: the page says nothing — whether a worker pool takes a sidecar is
  **unverified**.
- *Migrate alerting rules and receivers from Prometheus* — **verified**: `gcloud monitoring policies
  migrate --policies-from-prometheus-alert-rules-yaml=<files>`; no dry-run option; recording rules
  are not migrated (`ops/alerts.yaml` has none: 25 alerting rules, 0 recording).

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-039 (F-046)
Capability:      none — the deployment and the alerts' path
Inputs:          none
Tenant boundary: unchanged (labels are ids, never content; the platform adds only its own)
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged
Budget:          the API keeps its CPU always on (the sidecar's example does); a cost to watch
Failure mode:    none added to the service
Cache:           none
Safety:          the scrape config holds nothing secret; the label rules unchanged
Contract:        unchanged
Invariants:      unchanged
Blast radius:    LOCAL — deploy/, tools/checks, the Makefile, a runbook
Decision level:  1
ADR:             none
```

## What changed
- **`deploy/monitoring/run-gmp.yaml`**: a `RunMonitoring` scraping `9091` `/metrics` every 30 s.
  The ground stores it as the secret `catalyst-ai-run-gmp-config`.
- **API and worker manifests**: the service's container is named (`api`, `worker`), with a
  `collector` sidecar beside it (the platform's image, no environment) mounting that secret at
  `/etc/rungmp/`, and `container-dependencies` so the collector starts after the service. The API
  also gets `gen2` and CPU always on, as the documented example does. The sidecar image is by tag
  today and **must be pinned by digest before the first promotion**.
- **The deployment check** allows, beside the service's own container, the metrics sidecar alone:
  named `collector`, the platform's image, no environment. A container dressed as it, with another
  image or with environment variables, is still refused as a non-placeholder image.
- **`make alert-policies`** prints, never runs: `gcloud monitoring policies migrate
  --policies-from-prometheus-alert-rules-yaml=ops/alerts.yaml`.
- **The runbook's alerts section**: the path, the three steps before and after the first promotion,
  and the worker-pool doubt.

## The acceptance, point by point
- **The metrics path, verified or marked.** As above. The dry render of the three manifests gives
  `api` (8090) with `collector` and the config secret, `worker` with `collector`, and `migrate` alone.
- **Alerts on the exported names, thresholds unchanged.** `git diff ops/alerts.yaml` is empty: the
  names are queried unchanged, and every rule aggregates with `sum by (…)` on the service's own
  labels (`capability`, `operation`, `model`, `state`, `organization`), so the labels the platform
  adds are summed away and no threshold moves. The file is the migration's input as it stands.
- **Label rules hold.** The metrics module's label rules (`ARCH-010 §2`) and their tests pass
  unchanged; the export changes no label value.

## Red first
```
the sidecar exemption removed from the check
  deploy/run/api.yaml:1, deploy/run/worker.yaml:1: the image is not the placeholder   GATE RED
restored: deployment green; test_deployment (9) and the observability suite pass (29)
the runbook's first metric named catalyst_ai_requests_total — no such metric; corrected to
  catalyst_ai_http_requests_total (the name the alerts read)
```

## Proposal (not built): refuse an unknown `CATALYST_AI_*` variable at start
Today a mistyped setting is ignored and keeps its default (record 050, checked). Proposed: at start,
any environment variable with the `CATALYST_AI_` prefix that is not a setting refuses the process,
naming it. Development would warn instead. It is a start-time refusal like the others in
`config/deployed.py`. It waits for a decision, because a variable set by the platform with that
prefix would then need an allow-list.

## Eval and budget numbers
No capability changed; no eval set moved.

## Verify
Fast checks in the loop: the deployment and observability tests, lint, types, the static gate.
The full gate runs before this is pushed; its output is pasted here then.

The full gate on the tree this change is committed from:
```
$ make verify
VERIFY GREEN — GATE GREEN (56 checks) · 1189 passed, coverage 99.41% · EVALS GREEN · selftest 58/58 (on the host, before record 043's make hooks fix)
$ make ci
VERIFY GREEN in catalyst-ai-ci:d06a9811d6b3 — 56 checks · 1189 passed, 99.41% · EVALS GREEN · selftest 58/58 · stamp: tree f777f5806cb3 at 2026-09-25T07:16:19+00:00 -- green
```

## Decisions and questions
- `F-046` stays open until the first promotion shows a metric and the policies exist.
- The unknown-variable refusal: proposed above; built in session 053, refusing in development too.

## Commit
- `build(deploy): the metrics sidecar, so the alerts fire on Cloud Run`
