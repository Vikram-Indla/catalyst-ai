# 046 — The deployment manifests: the API, the worker and the migration, with no place and no credential written

**Date:** 2026-09-24 · **Ticket:** AI-036 (3 of 4: `deploy/`) · **Capability or package:** `deploy/` (Skaffold, three Cloud Run manifests), tools/checks (`deployment`, the gate's lists, the selftest), the change map, `RULE-006`, `F-045` · **Author:** a contributor

The service is made releasable to a staging environment on Cloud Run through Cloud Deploy. Nothing
is deployed from this change: it adds what a release deploys and the check that keeps it honest.

## Read
The Cloud Deploy and Cloud Run documentation, checked on 2026-09-24 (each point below is marked
**verified** or **unverified**):
- Cloud Deploy deploys Cloud Run services, jobs and worker pools. The location is the target's
  (`run.location`), never the manifest's. The image placeholder is replaced by `--images` at
  release creation. — **verified** (*Deploy an app to Cloud Run*)
- A manifest value marked `# from-param: ${name}` takes the target's, the pipeline stage's or the
  release's deploy parameter, for Cloud Run manifests too. — **verified** (*Deploy parameters*)
- Cloud Run v1 YAML: `autoscaling.knative.dev/minScale`, `run.googleapis.com/cpu-throttling`,
  `run.googleapis.com/ingress`, `serviceAccountName`, `containerPort`, the three probes with
  `httpGet.path`, `env[].valueFrom.secretKeyRef` — **verified** (*YAML reference v1*)
- Worker pools run continuous background work, need no endpoint and are generally available. —
  **verified** (*Deploy worker pools*). The delivery tool's own example still annotates one
  `launch-stage: BETA`; kept as in that example. — the annotation's necessity is **unverified**
- `me-central2` offering worker pools. — **unverified** from here (the location's service list is
  the Day 0 check); the fallback is written in `worker.yaml`
- Several manifests in one Skaffold profile, deployed in the order listed. — **unverified**
- Hook containers receive no environment variable naming the release's image. — **verified**
  (*Deploy hooks*). So "the migration job runs predeploy on the release's own digest" has no
  documented mechanism yet: an open question for the release path, not solved here.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-036 (deploy/, 3 of 4)
Capability:      none — the deployment
Inputs:          none
Tenant boundary: unchanged
Provider/model:  the capabilities off by default in the manifests (record 045's switch)
Prompt version:  unchanged
Eval set:        unchanged
Budget:          unchanged
Failure mode:    none added to the service; the check refuses a manifest that breaks a rule
Cache:           none
Safety:          no location, no credential value, one database login per process
Contract:        unchanged
Invariants:      INV-073's intent carried into the deployment (one login per process); F-045 open
Blast radius:    LOCAL — deploy/ and tools/checks
Decision level:  2 — a deployment shape; its migration step and F-045 wait for the lead
ADR:             none
```

## What changed
- **`deploy/skaffold.yaml`**: a `staging` profile listing the migration, the API and the worker;
  `deploy.cloudrun: {}`. The image is the placeholder `catalyst-ai`.
- **`deploy/run/api.yaml`** — a Service:
  - the contract port 8090; ingress `all` with the invoker role (the ground grants it to the
    backend's identity alone), plus the envelope;
  - probes: startup and readiness on `/health/ready` (503 until ready, record 044), liveness on
    `/health/live`;
  - `CATALYST_AI_CAPABILITIES_ENABLED` is `"false"` unless the target says otherwise (record 045);
  - its one database login from the secret `catalyst-ai-database-url`.
- **`deploy/run/worker.yaml`** — a WorkerPool, so the queue never stops for want of requests. The
  fallback is in its header: a Service with `minScale: "1"` and `cpu-throttling: "false"`. Its login
  is `catalyst-ai-database-worker-url`.
- **`deploy/run/migrate.yaml`** — a Job: `migrate`, `maxRetries: 0`, `timeoutSeconds: 600`, as the
  owner login (`catalyst-ai-database-migrate-url`).
- **Deploy parameters**: location, project, identities and the public verification key are all
  `# from-param:` values from the target. No location is written anywhere in `deploy/`.
- **`tools/checks/deployment`**, in the fast set, holds `deploy/run/*.yaml` to:
  - no written location;
  - the placeholder image;
  - credentials only as secret references;
  - every variable a setting the service reads;
  - no probe path ending in `z`;
  - at most one database login per process, no two sharing one;
  - a worker that cannot scale to zero.
  `RULE-006` has the row, and the selftest plants a rebuilt image, a written location, a
  credential value and `/healthz`: 58/58 red. The change map classes `deploy/*` as CONFIG.

## F-045 — found here, open
Outside development every process must today be given all three database URLs (D-052), so each can
prove at start that the logins differ. The manifests give each process **only its own**, as the
ground requires (each runtime identity reads only its own secret). As written, a deployed process
refuses to start until `F-045` is decided. The proposal is in the finding: each process requires
the URL it uses; the URLs it has must differ and none may be a development login; this check
already holds the three secrets distinct. Until then the manifests are ready but not startable, and
this record says so rather than giving the API every credential.

## Red first
```
the check's own tests (one per rule), before the empty-env fix
  test_a_probe_path_ending_in_z_is_refused, test_a_worker_service_must_keep_an_instance…   FAILED
  TypeError: 'NoneType' object is not iterable — an `env:` with no items read as None; fixed
each rule planted in a manifest: a written location, a credential value, an unknown variable,
  a rebuilt image, /healthz, two logins in one process, a shared login, a worker at zero   -> refused
after: deployment green on deploy/; the tools suite 138 passed; selftest 58/58
```

## Eval and budget numbers
No capability changed; no eval set moved.

## Verify
Fast checks in the loop: the tools suite, lint, types, the static gate, the selftest. The full
gate runs before this is pushed; its output is pasted here then.

The full gate on the tree this change is committed from:
```
$ make verify
VERIFY GREEN — GATE GREEN (56 checks) · 1189 passed, coverage 99.41% · EVALS GREEN · selftest 58/58 (on the host, before record 043's make hooks fix)
$ make ci
VERIFY GREEN in catalyst-ai-ci:d06a9811d6b3 — 56 checks · 1189 passed, 99.41% · EVALS GREEN · selftest 58/58 · stamp: tree f777f5806cb3 at 2026-09-25T07:16:19+00:00 -- green
```

## Decisions and questions
- `F-045` opened (the logins at start); the migration step's mechanism, an open question for the
  release path.

## Commit
- `build(deploy): Cloud Run manifests for the API, the worker and the migration`
  (the manifests, the Skaffold profile, the change map's `deploy/*` row, this record)
- `build(gate): the deployment check holds manifests to placeholders and secrets` (landed shortened
  from the 86-character line first proposed here; the message check allows 80)
  (the check and its tests; two commits, since together they exceed RULE-005's 400 lines)
