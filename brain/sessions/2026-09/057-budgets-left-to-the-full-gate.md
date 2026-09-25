# 057 — The commit-time eval run leaves the latency and cost budgets to the full gate

**Date:** 2026-09-25 · **Ticket:** AI-043 (1 of 2: the budgets) · **Capability or package:** `tools/evals.py` (`judge`, `main`), `RULE-005`, `RULE-006`, `D-065`, record 046's commit line · **Author:** a contributor

During the last landing a commit was refused because `documents-ingest` measured p95 15.3 s against
its 15 s budget while the machine ran other work. Alone the set measured 5.0 s, and the retry was
green. A timing budget measured at commit time on a shared workstation measures the machine, and a
refusal that the retry then hides is noise. The commit-time run now judges every grader floor and
only reports the latency and cost budgets. The full gate enforces them unchanged.

## Read
- `tools/evals.py`: `judge` returned grader floors, `overall` and both budgets as reds; `main` used
  it for `--affected` (the pre-commit) and for the full run alike.
- The budgets are also held by `tools/checks/budgets` (RULE-006) and by `make evals` in
  `make verify` and `make ci`. Neither changes.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-043 (1 of 2)
Capability:      none — the commit-time eval run
Inputs:          none
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged; no floor or budget moved
Budget:          unchanged; enforced where the run is alone (the full gate, hosted, nightly)
Failure mode:    a commit no longer fails on a timing it cannot measure fairly
Cache:           none
Safety:          unchanged
Contract:        unchanged
Invariants:      unchanged
Blast radius:    LOCAL — the eval runner and two rules
Decision level:  2 — D-065 (the lead)
ADR:             none
```

## What changed
- **`judge(result, floors, *, budgets=True)`**: the budgets are judged only when asked. `main`
  asks for them except under `--affected`, which prints the measured numbers with "reported only;
  the full gate, the hosted run and the nightly enforce it".
- **`RULE-005`** (the pre-commit's description) and **`RULE-006`** (the `make evals-affected` line)
  say so. **`D-065`** records it.
- **Record 046** quotes the commit message as it landed (77 characters), not the 86-character line
  first proposed.

## Red first
```
the budgets judged unconditionally
  test_the_commit_time_run_reports_the_budgets_but_never_fails_on_them   FAILED
restored: tests/unit/tools/test_evals_budgets.py 3 passed (the full gate still reds on both
  budgets; the commit-time run still reds on a grader floor)
```

## Eval and budget numbers
No set ran: the machine is shared tonight. No floor or budget changed.

## Verify
Fast checks: lint, types, the tests above, the static gate green (17 checks). The full gate, on
the tree this change is committed from:
```
$ make verify
VERIFY GREEN — GATE GREEN (56 checks) · 1217 passed, coverage 99.42% · EVALS GREEN · selftest 58/58 (on the host, on the final tree)
$ make ci
VERIFY GREEN in catalyst-ai-ci:d06a9811d6b3 — 56 checks · 1217 passed, 99.42% · EVALS GREEN · selftest 58/58 · stamp: tree 853cbf005fc8 at 2026-09-25T11:40:25+00:00 -- green
```

## Decisions and questions
- `D-065`, decided by the lead. It is the first step of scoping the commit-time checks; the rest is
  record 058, in the same commit (both change `tools/evals.py`).

## Commit
- with record 058: `build(gate): commit-time checks read the staged set, the tip stays whole`
