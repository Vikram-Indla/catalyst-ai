# 045 — The capabilities off, proven end to end

**Date:** 2026-09-24 · **Ticket:** AI-036 (2 of 4: capabilities off) · **Capability or package:** `config/settings.py` (`capabilities_enabled`), `platform/pipeline/door.py`, the config ledger, a contract test · **Author:** a contributor

Staging may come up before its region serves the models. Then the service runs with its
capabilities off: every capability refuses by design, while the probes, readiness and the jobs'
polling keep answering, so the backend and the product run around it. Each capability already
had its own kill switch; an environment wants one switch for all of them, and a proof that
nothing slips past it.

## Read
The door (`platform/pipeline/door.py`) every capability passes, the settings, the contract
document's operations, the eval sets' requests (`tools/evalkit.REGISTRY`), `RULE-003`.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-036 (capabilities off, 2 of 4)
Capability:      every capability's door; none changes in version
Inputs:          unchanged; one setting, CATALYST_AI_CAPABILITIES_ENABLED (default true)
Tenant boundary: unchanged
Provider/model:  off: never called
Prompt version:  unchanged
Eval set:        unchanged
Budget:          unchanged
Failure mode:    off: 503 ai.capability.disabled from every capability (an error frame on the stream)
Cache:           unchanged
Safety:          unchanged
Contract:        unchanged (the error code exists; no operation or field changes)
Invariants:      unchanged
Blast radius:    PLATFORM — config and platform/pipeline
Decision level:  1
ADR:             none
```

## What changed
- `capabilities_enabled` (`CATALYST_AI_CAPABILITIES_ENABLED`, default `true`): the environment's
  switch, checked by the door **before** each capability's own. Off, every capability refuses
  `ai.capability.disabled` ("the capabilities are off in this environment"); nothing else about the
  service changes. The config ledger has the row.
- **The proof** (`tests/contract/test_capabilities_off.py`):
  - it walks every operation the contract document declares for a capability (22 today, the job
    submissions included) and posts a request each would otherwise accept — the first case of its
    eval set, or a minimal index request — signed as the backend signs it, with a job window;
  - each answers `503 ai.capability.disabled`, or an `event: error` frame carrying that code on the
    stream;
  - `/health/live` and `/health/ready` answer 200, and the provider is never called;
  - an operation the contract gains without a request here fails the test by name.
- A job already queued meets the same door in the worker: a drafts item is skipped as `refused`
  with the code `ai.capability.disabled`, which the backend retries once the switch is on.

## Red first
```
the door's environment check removed
  test_every_capability_refuses_by_design_with_the_capabilities_off                      FAILED
  ('/v1/improve-story', '{"error":{"code":"ai.output.invalid", …}}')  — it reached the provider
restored: the contract and platform suites pass (339)
```

## Eval and budget numbers
No capability's behaviour changed with the switch on; no eval set moved.

## Verify
Fast checks in the loop: the contract and platform suites, lint, types, the static gate. The full
gate runs before this is pushed; its output is pasted here then.

The full gate on the tree this change is committed from:
```
$ make verify
VERIFY GREEN — GATE GREEN (56 checks) · 1189 passed, coverage 99.41% · EVALS GREEN · selftest 58/58 (on the host, before record 043's make hooks fix)
$ make ci
VERIFY GREEN in catalyst-ai-ci:d06a9811d6b3 — 56 checks · 1189 passed, 99.41% · EVALS GREEN · selftest 58/58 · stamp: tree f777f5806cb3 at 2026-09-25T07:16:19+00:00 -- green
```

## Decisions and questions
- None. The deployment sets `CATALYST_AI_CAPABILITIES_ENABLED=false` while the region's model list
  is unconfirmed (record 046's manifests carry it).

## Commit
- `feat(platform): one switch turns every capability off, proven end to end`
