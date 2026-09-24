# 041 — The change-aware push on Windows: the nested make never inherits the runner's uv

**Date:** 2026-09-24 · **Ticket:** AI-021 (F-043) · **Capability or package:** tools (`change_gate`), the Makefile · **Author:** a contributor

The end-of-loop push found that the change-aware gate broke on Windows (`F-043`). Split from
record 036, which carried it beside the list mode, so each commit names one ticket.

## Read
`tools/change_gate.py`, the Makefile, `.githooks/pre-push`, `RULE-005 §1`.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-021 (F-043)
Capability:      none — the push gate
Inputs:          the environment of the nested make
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged
Budget:          unchanged
Failure mode:    none added; a push on Windows no longer fails with a mangled uv path
Cache:           none
Safety:          unchanged
Contract:        unchanged
Invariants:      INV-071 unchanged
Blast radius:    LOCAL — tools and the Makefile
Decision level:  0
ADR:             none
```

## What changed
`.githooks/pre-push` → `make ci-aware` → `tools/change_gate.py`, which starts `make ci-scoped` as a
child. `uv run` exports `UV` as its own executable's path; the child make read it through
`UV ?= uv`, and on Windows bash stripped the path's backslashes (`C:UserswasimAppData…uv.exe:
command not found`). The push was refused. Nothing unproven went out; the tests had planned the
targets but never run the child, and the hosted runner and the image are Linux. The fix:
`change_gate.child_env()` gives every child the environment without `UV`, so the child make uses
the `uv` on PATH, as a make started by hand does. And the Makefile names `uv` itself (`UV := uv`,
no longer `?=`), so no other parent can inherit a path into a recipe; only the command line
(`make UV=…`) may name another. Still to show: one real `make ci-aware` on a docs-only change on
this Windows workstation, end to end, once the next full gate's stamp exists; its output goes here.

## Red first
```
the child environment, before the fix
  test_the_nested_make_never_inherits_the_runners_uv_path                            FAILED (no decide, no env)
a dry run of the child make from inside uv run, on this workstation
  inherited  -> C:\Users\…\uv.exe run --frozen python -m tools.ci_image require   (bash strips the path)
  child_env  -> uv run --frozen python -m tools.ci_image require
fixed: the change-gate tests pass
```

## Eval and budget numbers
No capability changed; no eval set moved. The full run of every set is in the gate output below.

## Verify
Fast checks in the loop: the tools suite, lint, types.

The full gate on the tree this change is committed from:
```
$ make verify
(ran before the one-line hermeticity fix to tests/unit/tools/test_commitsize.py that record
040 names; make ci below ran on the final code, that fix included)
582 files already formatted
All checks passed!
Success: no issues found in 582 source files
Contracts: 5 kept, 0 broken.
GATE GREEN (53 checks)
api\openapi.yaml matches the app
oasdiff: no breaking change against main
TOTAL                                                            8129     29   1030     25    99%
1137 passed in 177.40s (0:02:57)
GATE GREEN (1 checks)
-- assistant v1 - 83 cases
-- brief v1 - 14 cases
-- documents v1 - 92 cases
-- documents-generate v1 - 42 cases
-- documents-ingest v1 - 19 cases
-- generate-children v2 - 144 cases
-- generate-tests v1 - 89 cases
-- improve-story v3 - 80 cases
-- interpret-query v2 - 52 cases
-- post-mortem v1 - 45 cases
-- propose-workflow v1 - 46 cases
-- release-notes v1 - 90 cases
-- search v1 - 146 cases
-- summarize v3 - 251 cases
-- translate v2 - 104 cases
-- translate-drafts v1 - 9 cases
-- unfurl v1 - 6 cases
EVALS GREEN
GATE GREEN (1 checks)
No known vulnerabilities found
9:30PM INF no leaks found
GATE GREEN (1 checks)
selftest: 55/55 checks red on their plant
VERIFY GREEN
verify exit 0
$ make ci
582 files already formatted
All checks passed!
Success: no issues found in 582 source files
Contracts: 5 kept, 0 broken.
GATE GREEN (53 checks)
api/openapi.yaml matches the app
oasdiff: no breaking change against main
TOTAL                                                            8129     29   1030     25    99%
1137 passed in 311.22s (0:05:11)
GATE GREEN (1 checks)
-- assistant v1 - 83 cases
-- brief v1 - 14 cases
-- documents v1 - 92 cases
-- documents-generate v1 - 42 cases
-- documents-ingest v1 - 19 cases
-- generate-children v2 - 144 cases
-- generate-tests v1 - 89 cases
-- improve-story v3 - 80 cases
-- interpret-query v2 - 52 cases
-- post-mortem v1 - 45 cases
-- propose-workflow v1 - 46 cases
-- release-notes v1 - 90 cases
-- search v1 - 146 cases
-- summarize v3 - 251 cases
-- translate v2 - 104 cases
-- translate-drafts v1 - 9 cases
-- unfurl v1 - 6 cases
EVALS GREEN
GATE GREEN (1 checks)
No known vulnerabilities found
5:16PM INF no leaks found
GATE GREEN (1 checks)
selftest: 55/55 checks red on their plant
VERIFY GREEN
stamp: tree a68be55f2c88 in catalyst-ai-ci:d06a9811d6b3 at 2026-09-24T17:16:36+00:00 -- green
ci exit 0
```

## Decisions and questions
- `F-043` closed with the fix.

## Commit
Proposal 19 of the loop's list in record 037:
- `fix(gate): the change-aware push's nested make drops the runner's uv path`
