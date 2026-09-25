# Staging — running, switching off, rolling back and reading the service on Cloud Run

**Scope:** the staging environment on Cloud Run, released through Cloud Deploy (`deploy/`,
`make release`). **Alert:** none of its own. Read **Alerts** below before relying on any. Every
command marked **(verify)** follows the product documentation as read on 2026-09-24 but has not
been run against this environment. Confirm it the first time and delete the mark.

## What runs where

| Piece | Cloud Run resource | Login it reads | Released by |
| --- | --- | --- | --- |
| API (the contract, port 8090) | service `catalyst-ai` | `catalyst-ai-database-url` (serve) | pipeline `catalyst-ai` |
| Worker (jobs, indexing, retention) | worker pool `catalyst-ai-worker` | `catalyst-ai-database-worker-url` | pipeline `catalyst-ai` |
| Migration | job `catalyst-ai-migrate` | `catalyst-ai-database-migrate-url` (owner) | pipeline `catalyst-ai-migrate`, promoted first |

The location, the project, the identities and the public verification key come from the targets'
deploy parameters. None of them is written in the repository.

## Start — a release, promoted in order

1. `make release` on `main`: the image is built once, pushed, and two releases are created from its
   digest, `catalyst-ai-migrate-<commit>` then `catalyst-ai-<commit>`. The hosted job does the same
   print-only until its login is approved.
2. Promote `catalyst-ai-migrate-<commit>` in Cloud Deploy. Its postdeploy action runs the migration
   and waits. **(verify)** a failed migration turns the rollout red: confirm once with a planted
   failure before the first real promotion.
3. Promote `catalyst-ai-<commit>`. The API revision takes traffic only when its startup probe on
   `/health/ready` answers 200. That means the settings loaded, the database answered, the
   workload identity is current and the process is serving.

## Stop

The service is stopped by switching its capabilities off (next section), not by taking it down: the
backend then receives `ai.capability.disabled` and runs without it. To take a piece down entirely:
- API: remove the backend's invoker grant (the ground's IAM). The service stays deployed and
  refuses every caller.
- Worker: scale the worker pool to zero instances **(verify the command against the worker pool
  reference)**. Queued jobs wait and expire after their window (`job-backlog.md`).

## The capabilities switch

Staging starts with `CATALYST_AI_CAPABILITIES_ENABLED=false`, the targets' `capabilities_enabled`
deploy parameter, until the location's models are confirmed. Off:
- every capability answers `503 ai.capability.disabled` (on the assistant's stream, an `error`
  frame);
- `/health/live` and `/health/ready` answer 200, and the jobs' polling answers;
- the provider is never called.

This is proven on every operation by `tests/contract/test_capabilities_off.py`.

To turn them on:
- **The durable way:** set the targets' `capabilities_enabled` to `"true"`, then create and promote a
  new release. Deploy parameters are resolved when a release is created **(verify)**.
- **At once, until the next promotion:** `gcloud run services update catalyst-ai
  --update-env-vars=CATALYST_AI_CAPABILITIES_ENABLED=true` and the same on the worker pool
  **(verify)**. This makes a new revision outside the release; the next promotion puts back the
  target's value.

One capability alone is switched with its own `CATALYST_AI_CAPABILITY_<NAME>__ENABLED`
(`kill-switch.md`).

## Rollback — re-promote the previous release

In Cloud Deploy, promote the previous `catalyst-ai-<commit>` release again (or use the target's
rollback **(verify)**). It redeploys that release's digest in minutes. **Migrations are not rolled
back:** they are forward-only, and a release is rollback-safe only if its migrations were the
*expand* half. A migration marked incompatible needs a maintenance window, and its rollback is a
restore. Say so before promoting one.

## Reading logs

Each process writes one JSON object per line to standard output: `at`, `level`, `logger`,
`message`, and the request's `request_id`. Content fields are redacted. In Cloud Logging, filter on
the resource and on `jsonPayload.request_id`, the same id the backend logs for the call.
**(verify)** Cloud Logging reads a line's severity from a field named `severity`, and this service
writes `level`. Until that is confirmed, filter on `jsonPayload.level="ERROR"` rather than on
severity.

## Alerts — they fire once the metrics sidecar runs and the policies exist

The alert rules exist (`ops/alerts.yaml`, each with its page here: `CapabilityErrorBudgetBurn`,
`CapabilityLatencyHigh`, `RetrievalLatencyHigh`, `OutputRefusalsHigh`, `CacheHitRateLow`,
`ProviderFailing`, `ProviderLatencyHigh`, `TenantBudgetExhausted`, `JobQueueBacklog`,
`JobQuarantined`, `OriginForged`, `OriginRefusalsHigh`, `IndexUnavailable`, `OriginUnverifiable`).
They read `/metrics` on the ops port. Cloud Run exposes no second port, so the numbers leave
through the `collector` sidecar beside the API and the worker (`deploy/run/*.yaml`). The sidecar
scrapes `localhost:9091/metrics` as `deploy/monitoring/run-gmp.yaml` says, and writes to Cloud
Monitoring under the same metric names; the platform adds only its resource labels.

Before the first promotion:
1. Create the secret `catalyst-ai-run-gmp-config` from `deploy/monitoring/run-gmp.yaml`
   (`gcloud secrets create … --data-file=…`), readable by the API's and the worker's identities.
2. Pin the sidecar's image by digest.
3. After the first promotion, confirm a metric arrives (Metrics Explorer, PromQL
   `catalyst_ai_http_requests_total`), then create the policies with the command
   `make alert-policies` prints: `gcloud monitoring policies migrate
   --policies-from-prometheus-alert-rules-yaml=ops/alerts.yaml`. Names and thresholds are
   unchanged; that file is the source.

**(verify)** Whether a worker pool takes a sidecar is not stated in the documentation read. If it
does not, the worker's numbers (the job backlog, quarantine) stay unexported until a different
path is chosen. Until the policies exist (`F-046`), watch by hand after each promotion:
- `/health/ready` on the API;
- the 5xx rate in the request logs;
- the worker's log for `job` errors;
- `origin` refusals.

## A deployed process refuses to start

The revision never becomes ready and its log ends with the reason. The same check runs anywhere
with the same settings: `catalyst-ai check` (the image's own command) prints
`check: settings invalid` and the reason. Causes, by the message:

| Message | Cause | Fix |
| --- | --- | --- |
| the API: `DATABASE_WORKER_URL and DATABASE_MIGRATE_URL are required outside development`; the worker and the migration: `database_url  Field required` (checked) | **Expected today on Cloud Run** — each process is given only its own login, and the settings ask every process for serve's login and all three logins outside development (`F-045`, awaiting the lead's decision) | none until `F-045` is decided; do not give a process another's secret |
| `serve, the worker and the migration must log in as three different users` | two secrets name the same user | fix the secret, never the rule |
| `a login whose password is its user name is a development login` | a development credential reached staging | rotate the secret |
| `PROVIDER_VERTEX_LOCATION is required outside development` / `… is not an in-Kingdom location` | the target's `provider_location` is missing or wrong | fix the deploy parameter |
| `PROVIDER_VERTEX_PROJECT is required outside development` | the target's `provider_project` is missing | fix the deploy parameter |
| `a deployed process uses its workload identity, not a developer's token` | `CATALYST_AI_PROVIDER_ACCESS_TOKEN` is set | remove it |
| `HTTP_ADDR and OPS_ADDR must differ` | the manifest's addresses were edited | restore `:8090` / `:9091` |
| a public key error | `auth_public_keys` is not one or two `kid:base64url` Ed25519 keys | fix the deploy parameter; see `key-rotation.md` |

A **mistyped** or stale `CATALYST_AI_…` variable refuses the start too: `serve: unknown settings:
<names>; no setting has these names`. The names are printed, never the values. A nested setting is
spelt with two underscores (`CATALYST_AI_CAPABILITY_SUMMARIZE__ENABLED`). The tooling's own variables
(`config/unknown.py`, `TOOLING`) are the only allowed extras.

If the process starts but `/health/ready` stays 503, the body names the false check: `storage` (the
database or its network), `provider_credentials` (the workload identity) or `serving` (draining).
