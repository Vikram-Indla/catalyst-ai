# 049 — The migration's own pipeline: deployed and run before the service is promoted

**Date:** 2026-09-24 · **Ticket:** AI-036 (the migration step) · **Capability or package:** `deploy/skaffold-migrate.yaml` (new), `deploy/skaffold.yaml`, `deploy/run/migrate.yaml` (its header), `tools/release.py` (two releases), its tests · **Author:** a contributor

Record 046 left open how the migration runs before the service takes a new image: a hook cannot
name the release's image. The release owner chose the shape. The migration job gets its own
delivery pipeline, `catalyst-ai-migrate`: it deploys the job and runs it in a postdeploy action.
Both releases come from the one digest, and the lead promotes the migration's first.

## Read
Checked on 2026-09-24:
- *Deploy hooks* — **verified**: a hook is a Skaffold `customActions` entry run in a container,
  named in the pipeline stage's `predeploy` / `postdeploy`; its container receives
  `CLOUD_RUN_PROJECT` and `CLOUD_RUN_LOCATION` among others, and no variable naming the release's
  image.
- `gcloud run jobs execute` — **verified**: `[JOB] [--region] [--async | --wait]`; `--wait` "wait
  until the execution has completed running before exiting". Whether a **failed** execution makes it
  exit non-zero is **not stated**, and the rollout failing on a failed migration rests on it.
- The pipeline stage that names the action (`postdeploy`) is the ground's, outside the repo.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-036 (the migration step)
Capability:      none — the release
Inputs:          unchanged
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged
Budget:          unchanged
Failure mode:    a failed migration fails the migration's rollout; the service's release stays
                 unpromoted (the exit code is to be confirmed, above)
Cache:           none
Safety:          the job runs as the owner login alone (record 046); nothing written in the repo
Contract:        unchanged
Invariants:      unchanged
Blast radius:    LOCAL — deploy/ and tools
Decision level:  1
ADR:             none
```

## What changed
- **`deploy/skaffold-migrate.yaml`**: a `staging` profile with `run/migrate.yaml` only, and the
  custom action `migrate-execute`, which runs `gcloud run jobs execute catalyst-ai-migrate --wait` in
  the job's project and location as the platform passes them. The action's image is the gcloud CLI
  image, **to be pinned by digest before the first promotion** (not pinned here: its digest was not
  verified from here).
- **`deploy/skaffold.yaml`**: the API and the worker only.
- **`make release`** creates both releases from one digest, the migration's first:
  `catalyst-ai-migrate-<commit>` (pipeline `catalyst-ai-migrate`, `--skaffold-file=skaffold-migrate.yaml`),
  then `catalyst-ai-<commit>`. Both are 52–60 characters; the name rule's limit is **unverified**.
- The deployment check (record 046) still reads every manifest under `deploy/run/`, so the job
  keeps its one login.

## Red first
```
the release tests, before the second release existed
  test_the_steps_build_once_push_read_the_digest_then_create_the_release   (expected two creates) FAILED
after: 5 creates in order (build, push, inspect, migrate release, service release); tools suite 150
make release --print: both releases printed, the migration's first, one digest
```

## Before the first promotion (the ground's checklist)
- Pin the action's image by digest.
- Plant a failing migration once on staging and confirm the migration's rollout goes red, i.e.
  that `--wait` exits non-zero on a failed execution. If it does not, the action must read the
  execution's result instead.

## Eval and budget numbers
No capability changed; no eval set moved.

## Verify
Fast checks in the loop: the tools suite, lint, types, the fast gate. The full gate runs before
this is pushed; its output is pasted here then.

The full gate on the tree this change is committed from:
```
$ make verify
VERIFY GREEN — GATE GREEN (56 checks) · 1189 passed, coverage 99.41% · EVALS GREEN · selftest 58/58 (on the host, before record 043's make hooks fix)
$ make ci
VERIFY GREEN in catalyst-ai-ci:d06a9811d6b3 — 56 checks · 1189 passed, 99.41% · EVALS GREEN · selftest 58/58 · stamp: tree f777f5806cb3 at 2026-09-25T07:16:19+00:00 -- green
```

## Decisions and questions
- None; the shape is the release owner's.

## Commit
- `build(deploy): the migration's own pipeline, run before the service is promoted`
