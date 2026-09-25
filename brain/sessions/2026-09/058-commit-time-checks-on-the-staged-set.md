# 058 — The commit-time checks read what the commit changed; the tip is still checked whole

**Date:** 2026-09-25 · **Ticket:** AI-043 (2 of 2: the staged set) · **Capability or package:** `tools/scope.py` (new), `tools/precommit.py` (new), `tools/checks/gate.py` (`--staged`, `PER_FILE`, the scope), `tools/checks/vocabulary.py`, `tools/evals.py` (`--staged`), `tools/checks/commitsize.py` (the line total retired), the
Makefile (`verify-fast`), `RULE-005`, `RULE-006`, `D-066`, `D-067` · **Author:** a contributor

A one-file commit re-checked the whole repository. It re-formatted and re-linted every file, ran
the seventeen fast checks over every file, and re-ran every eval set the branch had touched since
`main`. So a series of commits paid the whole gate at every commit. Now the pre-commit reads the
staged set, and each step runs on what the commit changed, narrowed or whole but never skipped.
The full gate on the tip is unchanged.

## Read
Timed on 2026-09-25, one process at a time, on a machine that was also running another gate (so
indicative, not a benchmark):
- ruff format and ruff check over the repository: ~0.6 s each;
- mypy on its warm cache: ~7 s;
- the seventeen fast checks: ~26 s together, of which `vocabulary` was 7.3 s, `funcbudget` and
  `naming` ~1.8 s each, `filebudget` and `comments` ~1 s each;
- the eval sets: under `--affected` they are chosen by "changed since `main`", so in a series of
  commits every set runs at every commit.

Every per-file check finds its files through `walk` or `python_files` in the gate kernel, except
`vocabulary`, which walks itself. So one scope, set by the runner, narrows them all.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-043 (2 of 2)
Capability:      none — the commit-time checks
Inputs:          the staged set (git's index)
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged; the commit runs the sets its staged files can move
Budget:          unchanged (record 057)
Failure mode:    a commit is judged on what it changed; the ground moving runs everything
Cache:           mypy's incremental cache, as before
Safety:          nothing skipped; the tip still passes the whole gate before a push
Contract:        unchanged
Invariants:      unchanged
Blast radius:    LOCAL — the gate's tooling and two rules
Decision level:  2 — D-066 (the lead)
ADR:             none
```

## What changed
- **`tools/scope.py`**: `staged()` returns the index's added, copied, modified and renamed paths. A
  deleted file has nothing left to check. `needs_full()` is true for nothing staged, or for any of
  `pyproject.toml`, `uv.lock`, the Makefile, `mypy.ini`, `.importlinter`, the hooks,
  `tools/rules.py`, `tools/checks/` and the scoping tools themselves. `scope_of()` gives the
  staged files, or None for the whole repository.
- **The gate**: `--staged` sets the scope for the **per-file** checks (`PER_FILE`: `filebudget`,
  `funcbudget`, `comments`, `naming`, `globals`, `vocabulary`, `network`, `logs`, `inline`,
  `mypy_overrides`) through a context variable that `walk` and `vocabulary` read. The cross-file
  checks (`structure`, `dupl`, and the ones that read fixed files) always read the whole
  repository. The green line says how many staged files the per-file checks read.
- **`tools/evals.py --staged`**: the sets the staged files can move (the existing
  `affected_sets`), judged on their grader floors.
- **`tools/precommit.py`**, the one entry point the hook and a record's gate share:
  1. ruff format and check on the staged Python files of `src`, `tests` and `tools`;
  2. mypy on the whole program, on its cache (a change can break a file that did not change);
  3. the scoped gate;
  4. the scoped evals.
  A change that moves the ground runs every file; nothing staged runs the previous whole set.
- **What the commit holds, not what the disk holds.** The checks read files from disk, so a file
  staged in part (its working copy differs from the index) is refused, named, rather than judged
  on content the commit will not contain.
- **Every run says why it is scoped or whole** (`precommit: 2 staged files`, `precommit: every
  file: uv.lock moves what every file is judged by`, `precommit: 1 staged deletions and nothing
  else`).
- **A deleted Python module still runs the type check**, which finds every file that imported it.
  A renamed one is staged under its new name, so it runs anyway.
- **The escalation set needs nothing more for the contract document or the generated ledgers:**
  no fast check reads them (searched), so they are judged whole by the full gate, as before.
- **`commitsize`: one task per commit, one subject line** (`D-067`). The total of 400
  hand-written lines per commit and its exception are retired; each file keeps its own budget.
  The check now holds one ticket across the staged records, a message of one non-comment line
  (the `commit-msg` hook passes it the whole message), and the `gen:` rule. Its selftest plant
  carries two tickets, a second line and a mixed `gen:`.
- **`make verify-fast`** calls it, then gitleaks on the staged tree, as before.
- **`RULE-005`** (the pre-commit) and **`RULE-006`** (the `verify-fast` line and the ⚡ note) say so.
  **`D-066`** (decided by the lead) records it.

## Red first
```
the scope ignored (in_scope always true)
  test_a_per_file_check_reads_only_the_scope   FAILED (the untouched file's violation reported)
the full-set triggers ignored
  test_a_change_to_a_rule_config_lockfile_or_check_runs_every_file   6 FAILED
a file staged in part not detected
  test_a_file_staged_in_part_is_found_and_a_whole_one_is_not   FAILED
a deleted module not sent to the type check
  test_a_deleted_module_still_runs_the_type_check_that_finds_its_importers   FAILED
a second message line not refused
  test_the_message_is_one_subject_line_and_nothing_after_it   FAILED
restored: test_scope 15 passed, test_commitsize 7 passed, test_evals_budgets 3 passed; the
  tools suite 169 passed; selftest 58/58; the shared git config unchanged after the
  temporary-repository tests (no core.worktree, filemode false)
```

## The acceptance, point by point
- **A one-file commit, measured before and after** (2026-09-25, the machine free, the same tree,
  gitleaks not included in either):
  ```
  before: the previous recipe (ruff, ruff, mypy, the fast gate, evals --affected)  204.2 s
          evals chose every one of the 17 sets: the branch had touched shared code since main
  after:  tools/precommit.py, one staged test file                                   23.9 s
  after:  tools/precommit.py, one staged record                                      18.8 s
          'precommit: 1 staged files' · per-file checks on 1 staged file · eval sets []
  ```
  What remains is the whole-program type check on its cache and the cross-file checks, which
  read the whole repository by design. A change inside a capability runs that capability's sets
  too, and a change to shared code or a rule runs everything.
- **Per-file on the staged set, cross-file whole or incremental:** tested above.
- **A config, rules or lockfile change runs the full set:** tested above.
- **The full gate on the tip unchanged:** `make verify` and `make ci` are untouched, and their
  output is pasted below before the push.

## Eval and budget numbers
No set ran (the machine is shared); no floor or budget changed.

## Verify
Fast checks: lint, types, the import contracts (5 kept), the tests above, the static gate green
(17 checks). The full gate, on the tree this change is committed from:
```
$ make verify
VERIFY GREEN — GATE GREEN (56 checks) · 1217 passed, coverage 99.42% · EVALS GREEN · selftest 58/58 (on the host, on the final tree)
$ make ci
VERIFY GREEN in catalyst-ai-ci:d06a9811d6b3 — 56 checks · 1217 passed, 99.42% · EVALS GREEN · selftest 58/58 · stamp: tree 853cbf005fc8 at 2026-09-25T11:40:25+00:00 -- green
```

## Decisions and questions
- `D-066` and `D-067`, decided by the lead.
- The push side (the affected pre-push, the red-main rule) and the step caches follow as their
  own changes.

## Commit
- with record 057: `build(gate): commit-time checks read the staged set, the tip stays whole`
