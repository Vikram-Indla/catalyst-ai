# 040 — The commit-size rule gets its check

**Date:** 2026-09-24 · **Ticket:** AI-035 · **Capability or package:** tools/checks (`commitsize`, the gate's lists, the selftest), `.githooks/commit-msg`, `RULE-005`, `RULE-006` · **Author:** a contributor

`RULE-005 §1` says a commit is one ticket and at most 400 changed hand-written lines, and
nothing checked it: `commitclass` judges a record's radius, not the size of what it is committed
with. Measuring the loop's pending change set found three proposals of 800 to 1 200 lines each. A
rule without its check breaks `RULE-006`'s own premise, so the check comes first.

## Read
`RULE-005`, `RULE-006` (every rule names its check), `tools/checks/commitclass`,
`tools/checks/commits` (what is generated), `tools/rules.GENERATED_PATHS` and
`GENERATED_LEDGERS`, the hooks.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-035
Capability:      none — the gate
Inputs:          the staged diff, the staged records, the decisions log, the commit message
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged
Budget:          unchanged
Failure mode:    a commit over 400 hand-written lines, with two tickets, or a `gen:` commit holding a
                 hand-written path is refused at pre-commit or commit-msg, with the count and the
                 three biggest files
Cache:           none
Safety:          no skip flag, no environment switch; the only exception is a lead-decided `D-NNN`
Contract:        unchanged
Invariants:      none added (RULE-006's row names the check)
Blast radius:    LOCAL — tools/checks and the hooks
Decision level:  1
ADR:             none
```

## What changed
- **`tools/checks/commitsize`**, in the fast set, so the pre-commit hook runs it. It measures the
  staged diff: added plus deleted lines of every path `commits.is_generated` does not class as
  generated. That excludes the lockfile, the contract document, the fixtures and the ledgers the
  rules name as generated; `set.jsonl` is hand-written by those rules and counts. It reads the
  ticket from each staged record's `**Ticket:**` field, up to the first `·`, and refuses two.
  Refusals give the count and the three biggest files.
- **With the message** (`.githooks/commit-msg` calls it), a `gen:` commit may hold generated paths
  only.
- **The exception** is a decision the lead took. The staged record names it
  (`**Size exception:** D-NNN`), and `brain/02-DECISIONS.md` holds that row with `lead` in the
  "By" column (not `lead (proposed)`) and naming RULE-005. A test greps the module for a
  `--skip`, an environment variable or a second argument: none.
- `RULE-005 §1` says how it is measured; `RULE-006` has the row; the selftest plants an
  over-size, two-ticket, mixed `gen:` commit: 55/55 red.

## Red first
```
the limit raised to 4 000          -> 3 tests FAILED (the line limit, the exception, the staged diff)
the gen: rule removed              -> 2 tests FAILED (gen purity, the staged diff with a message)
any named decision accepted        -> test_only_a_decision_the_lead_took_excuses_the_size… FAILED
restored: 8 passed; the tools suite 121; selftest 55/55 (commitsize red with 3 on its plant)
```
The first `make ci` found the staged-diff test not hermetic: in the image `GIT_DIR` and
`GIT_WORK_TREE` point at the mounted repository, so the test's `git init` and `git add` in a
temporary folder addressed the real one and `add` failed (`assert None is not None`). The test
now clears the git environment for its folder; run again with both variables set: 8 passed.
Worse, that `git init` ran with `GIT_WORK_TREE` set and wrote `core.worktree = /work` into the
repository's shared config, which made the next run judge the wrong tree (`sessions` red on
records 010–024) and broke the local main checkout. The key was removed, restoring the config
as it was, and `core.filemode`, which the same `git init` had re-probed on the image's mount
and set to `true` (every file then read as changed there), went back to `false`; the hermetic
test cannot write either again.

## What it finds in the pending proposals
Record 036 names two tickets (`AI-031, AI-021`), so a commit carrying it is refused, correctly.
Split, the F-043 section goes to its own record committed with the gate fix. Proposals 18, 20 and
22 are over the lines; the split plan is in the lead's hands. This check is proposed to commit
first, so that every later commit of the loop meets it.

## Eval and budget numbers
No capability changed; no eval set moved. The full run of every set is pasted with the next full
gate.

## Verify
Fast checks in the loop: the tools suite, lint, types, the fast gate (14 checks), the selftest.
The full gate (verify, then ci in the image) runs next; its output is pasted here then.

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
- None. The rule is RULE-005's; this is its check.

## Commit
- `build(gate): check the commit-size rule — one ticket, 400 lines, gen: only`
