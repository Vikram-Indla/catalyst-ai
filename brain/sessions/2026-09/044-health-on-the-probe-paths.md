# 044 — Health on the paths a platform's probe uses; the platform's header never a credential

**Date:** 2026-09-24 · **Ticket:** AI-036 (1 of 4: health) · **Capability or package:** `app.py` (two probe routes), `platform/auth` (the exempt paths), `tools/checks/latency`, the contract document · **Author:** a contributor

The service is being made releasable to staging on Cloud Run (nothing is deployed from this
change). Cloud Run probes one container port with HTTP checks that read only the status code, and
it reserves some URL paths ending in `z`. The service already served `/healthz` and `/readyz` on
its contract port, but `/readyz` answers 200 even when not ready (its verdict is in the body), so a
startup or readiness probe on it would always pass.

## Read
The Cloud Run documentation, checked on 2026-09-24:
- *Configure container health checks*: startup, liveness and readiness probes, HTTP on the container
  port;
- *Known issues*: "Some paths ending with `z` … we recommend avoiding all paths that end in `z`";
- *Service-to-service authentication*: `X-Serverless-Authorization` is checked instead of
  `Authorization` when both are present, and the platform "removes the signature before passing the
  token to the user container".

Also `app.py`'s health routes, `platform/auth/middleware.py`, the health and origin contract tests.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-036 (health, 1 of 4)
Capability:      none — the platform
Inputs:          none (two GET probes)
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged
Budget:          none (probes; latency.py names why)
Failure mode:    /health/ready answers 503 when any check is false
Cache:           none
Safety:          the probes return no tenant data; the envelope still read only from Authorization
Contract:        CHANGE, additive — health.probe_live, health.probe_ready; oasdiff: no breaking change
Invariants:      unchanged
Blast radius:    PLATFORM — platform/auth's exempt paths
Decision level:  1
ADR:             none
```

## What changed
- `GET /health/live` (`health.probe_live`) and `GET /health/ready` (`health.probe_ready`): the same
  checks as `/healthz` and `/readyz`, on paths that do not end in `z`. `/health/ready` answers **503**
  with the same body when not ready. Both are exempt from the envelope and served on the contract
  port and on the ops port. That covers the worker too: on Cloud Run its one port is its ops port.
- `/healthz` and `/readyz` are unchanged, kept for local use (the local-up contract calls
  `9091/healthz`).
- `X-Serverless-Authorization`: the middleware reads the envelope from `Authorization` only, and a
  test fixes it. An envelope sent only in the platform's header is refused. A platform token beside a
  valid envelope changes nothing.

## Red first
```
the new paths removed from the exemption
  test_the_probe_paths_need_no_proof, test_health_probe_live_…, test_health_probe_ready_… (×2)   FAILED
the probe answering 200 whatever the checks say
  test_health_probe_ready_answers_503_with_its_checks_when_not_ready                          FAILED
restored: the health, origin and platform suites pass (222)
```

## Eval and budget numbers
No capability changed; no eval set moved.

## Verify
Fast checks in the loop: the contract and platform suites, lint, types, the static gate, oasdiff
against main. The full gate runs before this is pushed; its output is pasted here then.

The full gate on the tree this change is committed from:
```
$ make verify
VERIFY GREEN — GATE GREEN (56 checks) · 1189 passed, coverage 99.41% · EVALS GREEN · selftest 58/58 (on the host, before record 043's make hooks fix)
$ make ci
VERIFY GREEN in catalyst-ai-ci:d06a9811d6b3 — 56 checks · 1189 passed, 99.41% · EVALS GREEN · selftest 58/58 · stamp: tree f777f5806cb3 at 2026-09-25T07:16:19+00:00 -- green
```

## Decisions and questions
- None. Recorded in the contracts changelog (AI-036).

## Commit
- `feat(platform): liveness and readiness on the probe paths, 503 when not ready`
