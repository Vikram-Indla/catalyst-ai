# 061 — Commit and push in seconds; the gate runs after the push

**Date:** 2026-10-10 · **Ticket:** AI-048 · **Capability or package:** `.githooks/pre-push`, `tools/precommit.py`, `.github/workflows/ci.yml`, the Makefile (`verify-push`, `nightly`), `tools/checks/ci`, `tools/checks/sessions`, `tools/rules.py`, RULE-005, RULE-006, `ENGINEERING.md`, the session template, `D-069` · **Author:** a contributor

The lead's rule: a commit and its push take seconds. The pre-commit ran the whole type check and
every eval set a staged check could move (505 s on the release-job commit); the pre-push consulted
the stamp and then ran `make ci-aware` in the CI container. Both now take seconds, and the gate
runs on the hosted runner after the push, split into a per-push set under ten minutes and the
nightly.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-048
Capability:      none — the hooks, the workflows and the rules that describe them
Inputs:          none
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged; runs nightly with its budgets instead of at commit and per push
Budget:          unchanged; enforced nightly
Failure mode:    a regression the commit no longer catches is caught by the next hosted run
Cache:           none
Safety:          a secret is still refused at commit (staged tree) and at push (pushed range)
Contract:        unchanged
Invariants:      INV-040 reworded
Blast radius:    PLATFORM — every contributor's commit and push
Decision level:  2 — D-069 (the lead)
ADR:             none
```

## Changed
- `.githooks/pre-push` — refuses every ref but `main`; gitleaks on `<remote>..<local>` (the
  pushed commits when the ref is new). No stamp, no `ci-aware`, no Docker.
- `tools/precommit.py` — ruff on the staged set and the gate's fast checks; no mypy, no evals.
- `Makefile` — `verify-push` (lint, api-check, ledgers-check, test, coverage-check, security,
  selftest); `verify` = `verify-push` + storage, drills, evals, budgets-check; `nightly` gains the
  drills, the evals and the budgets.
- `ci.yml` — `make verify-push`; `concurrency` on the ref with `cancel-in-progress`.
- `tools/checks/ci`, `tools/rules.py` — pin both; a run of `make verify` per push is refused.
- `tools/checks/sessions` and the template — a record names its tests (`## Tests run`).
- RULE-005 §1, §2, §4; RULE-006 §2 and §3; `ENGINEERING.md` steps 5 and 7 and invariant 10;
  ARCH-011's hook line; INV-040.

## Tests run
- `pytest tests/unit/tools/test_ci_workflows.py tests/unit/tools/test_ci_image.py tests/unit/tools/test_scope.py tests/unit/tools/test_release_job.py` — 37 passed
- `python -m tools.checks.gate --only ci` — ok
- the two new plants (`cancel-in-progress: false`; `make verify` per push) red

## Eval and budget numbers
No capability touched.

## Decisions and questions
- D-069 filed.

## Commit
Line: `ci(gate): commit and push in seconds; the full gate runs after the push`

## Next
Read the first hosted per-push run's duration against the ten-minute budget.
