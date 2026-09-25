# 043 — The gate's image reads git and never writes it

**Date:** 2026-09-24 · **Ticket:** AI-038 · **Capability or package:** the Makefile (`CI_GIT`), tools/checks (`gitmount`, the gate's lists, the selftest), `RULE-006` · **Author:** a contributor

At the last landing a test inside the gate's image inherited `GIT_DIR` and `GIT_WORK_TREE`, ran
`git init`, and wrote `core.worktree` and `core.filemode` into the repository's shared config,
which broke the local main checkout and made the next run read every file as changed (record 040).
The test was fixed; the defence belongs to the gate: the image had the git common directory
mounted writable, so any step could do the same again.

## Read
The Makefile's `ci` and `ci-scoped` recipes, `tools/stamp` (host side), record 040, `RULE-006`.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-038
Capability:      none — the gate
Inputs:          unchanged
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged
Budget:          unchanged
Failure mode:    a step inside the image that writes git fails with a read-only error
Cache:           none
Safety:          the repository's git config and index cannot be changed from inside the image
Contract:        unchanged
Invariants:      none added (RULE-006's row names the check)
Blast radius:    LOCAL — the Makefile and tools/checks
Decision level:  0
ADR:             none
```

## What changed
- **`CI_GIT`**, one definition used by both `docker run` lines: the git common directory mounted
  `:ro`, `GIT_DIR` and `GIT_WORK_TREE` as before, and `GIT_OPTIONAL_LOCKS=0` so no status, diff or
  log refreshes the index. The stamp (`tools.stamp begin` / `write`) is written on the host, before
  and after the container, as it was; nothing in the image writes git.
- **`tools/checks/gitmount`**, in the fast set: every `:/gitcommon` mount in the Makefile is `:ro`,
  and a Makefile that mounts it names `GIT_OPTIONAL_LOCKS=0`. `RULE-006` has the row; the selftest
  plants a writable mount without the switch: 57/57 red.

## Red first
```
inside the image, the common directory mounted :ro, GIT_OPTIONAL_LOCKS=0 (a seconds-long probe):
  $ git config core.worktree /x
  error: could not lock config file /gitcommon/config: Read-only file system   (exit 255)
  git status: exit 0 · git log: 15adf02 …  (reads unaffected)
  the host's config checksum identical before and after
main's Makefile under the new check
  Makefile@main:133: the git common directory is mounted writable
  Makefile@main:144: the git common directory is mounted writable
  Makefile@main:1: git runs in the image without GIT_OPTIONAL_LOCKS=0
after: gitmount green; make -n ci expands to :/gitcommon:ro and GIT_OPTIONAL_LOCKS=0; selftest 57/57
```
The full run in the read-only image is the next full gate (with record 042's), when Docker is free:
it is the proof that no step of the pipeline needs to write git.

## Eval and budget numbers
No capability changed; no eval set moved.

## Verify
Fast checks in the loop: the tools suite, lint, types, the fast gate, the selftest. The full
gate runs before this is pushed; its output is pasted here then.

The full gate on the tree this change is committed from:
```
$ make verify
VERIFY GREEN — GATE GREEN (56 checks) · 1189 passed, coverage 99.41% · EVALS GREEN · selftest 58/58 (on the host, before record 043's make hooks fix)
$ make ci
VERIFY GREEN in catalyst-ai-ci:d06a9811d6b3 — 56 checks · 1189 passed, 99.41% · EVALS GREEN · selftest 58/58 · stamp: tree f777f5806cb3 at 2026-09-25T07:16:19+00:00 -- green
```

## Decisions and questions
- None.

## Commit
- `build(gate): the image mounts git read-only and takes no optional lock`
