# 011 — gate economy: warm caches in the image, a stamp for the push, iteration targets

**Date:** 2026-09-23 · **Ticket:** AI-012 · **Capability or package:** Makefile, .githooks, tools/stamp, tools/affected, tools/evals · **Author:** a contributor

## Read
`RULE-005 §1`, `RULE-006 §2` and the target list, `tools/checks/ci`, `tools/ci_steps`, the `ci`
target (a throwaway `/tmp` inside the container held uv's cache and the project environment, so
every run re-resolved and re-installed before a check ran; the pre-push hook then ran the same
pipeline again on the tree `make ci` had just proven), `pytest.ini` (the cache provider off for
determinism), uv's cache documentation (`UV_CACHE_DIR`, `UV_PROJECT_ENVIRONMENT`, `UV_LINK_MODE`),
ruff's and mypy's cache variables.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-012
Capability or package: Makefile (ci, ci-cold, stamp-check, test-fast, evals-affected, verify-fast) · .githooks/pre-push ·
                 tools/stamp.py · tools/affected.py · tools/evals.py (--affected) · RULE-005 §1 and RULE-006 wording
Inputs:          none (no request surface)
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged — every set still runs in `make verify` and `make ci`; `--affected` is for `verify-fast` only
Budget:          unchanged
Failure mode:    a stale stamp honoured → a tree pushed without its own run; refused by keying the stamp on every tracked and
                 unignored file's content plus the image digest, and a day's age; a cache shared between host and container
                 corrupting itself → refused by separate cache directories (the mypy sqlite cache did corrupt once, F-019)
Cache:           three named volumes (uv cache, project environment, ruff/mypy/hypothesis caches); pytest's cache stays off in
                 the gate, on only in test-fast
Safety:          nothing leaves the machine; the stamp holds a hash, an image id and a time
Contract:        unchanged
Invariants:      INV-002 (CI equals the gate) unchanged; the check list unchanged (diff below)
Blast radius:    LOCAL — build files, hooks, tools, two rule pages' wording (versions 1.1.0)
Decision level:  1
ADR:             none — pytest-xdist measured and not taken (below)
```

## Changed
- `Makefile` — `ci` mounts `catalyst-ai-ci-uv:/tmp/uv-cache`, `catalyst-ai-ci-venv:/tmp/venv`, `catalyst-ai-ci-cache:/tmp/.cache` (with `RUFF_CACHE_DIR`, `MYPY_CACHE_DIR`, `HYPOTHESIS_STORAGE_DIRECTORY` under it; pip-audit's own cache lands there through `HOME=/tmp`), and green, writes the stamp; `ci-cold` drops the volumes first; `stamp-check`; `test-fast` (the unit tree, `--lf --ff -x`, no coverage, the cache provider on for this target only); `evals-affected`; `verify-fast` = lint-fast · evals-affected · gitleaks, its green line saying it is not evidence
- `.githooks/pre-push` — asks `stamp-check` first: a matching stamp prints and the push proceeds with no second run; otherwise `make ci` (or `make verify` without Docker, as before)
- `tools/stamp.py` — `tree_hash` (every tracked and untracked-but-not-ignored path with its on-disk blob id; a deletion counts), `image_digest`, `write`, `reason_to_run` (tree, image, age), `main` (`write` / `check` / `tree`); the stamp is `ci-green` in the common git directory, so a run in the worktree covers the push from the main checkout of the same tree
- `tools/affected.py` — the sets a change can move: a capability's own sets (its package, its `evals/<set>/`, its fixtures); everything when platform, providers, retrieval, contract, config, the app, the lock or the tooling outside `tools/checks/` moved; nothing for docs, tests and the checks
- `tools/evals.py` — `selected` (`--set`, `--affected`, or all)
- `tests/unit/tools/test_stamp.py`, `tests/unit/tools/test_affected.py`
- `docs/02-rules/RULE-005-git-and-sessions.md` 1.1.0 (the push rule: "a push is preceded by a green pipeline run of that tree; the stamp proves the tree"; the iteration targets named as never evidence), `docs/02-rules/RULE-006-enforcement.md` 1.1.0 (the push row, the target list, the cache paragraph)

## Verify
```
$ make verify
ruff / mypy (389 files + each set's graders) / lint-imports   All checks passed! · Success · Contracts: 5 kept, 0 broken.
tools.checks.gate --skip coverage,budgets                     GATE GREEN (43 checks)
tools.api · oasdiff                                           matches the app · no breaking change against main
pytest tests/architecture · pytest --cov                      24 passed · 639 passed in 182.09s · Total coverage: 99.45% · GATE GREEN (1 checks)
pytest tests/storage · make evals · budgets                   4 passed · EVALS GREEN (twelve sets unchanged) · GATE GREEN (1 checks)
pip-audit / gitleaks / licences · selftest                    No known vulnerabilities found · no leaks found · GATE GREEN · 45/45 red on their plant
VERIFY GREEN                                                  (wall 460 s on this machine)
```
```
$ make ci
$ make ci     (python:3.12.14-slim, the workflow's steps verbatim, the named volumes warm — the third run of the sequence)
All checks passed! · Success: no issues found in 389 source files · Contracts: 5 kept, 0 broken.
GATE GREEN (43 checks) · oasdiff: no breaking change against main
639 passed in 288.06s · Total coverage: 99.45% · GATE GREEN (1 checks) · pytest tests/storage: 4 passed
EVALS GREEN · GATE GREEN (1 checks) · No known vulnerabilities found · no leaks found · GATE GREEN (1 checks)
selftest: 45/45 checks red on their plant
VERIFY GREEN
stamp: tree 0a7b7366078d in python:3.12.14-slim at 2026-09-21T14:01:34+00:00 -- green            (wall 809 s)
```

## Before and after
| Run | Before (main's Makefile) | After |
| --- | --- | --- |
| `make ci`, cold (no volumes / volumes dropped) | 1 047 s | 948 s (`make ci-cold`) |
| `make ci`, second run on the unchanged tree | 1 047 s (every run is cold) | 809 s (the environment build gone; the suite itself 288 s vs 303 s under the mount) |
| push after a green `make ci` of the same tree | a second full pipeline | `stamp-check` in ~1 s, no run — transcript below |
| one edited file, then push | a full pipeline | `stamp: the tree changed since its last green run` → `make ci` |
| `make verify`, local, unchanged tree | ≈ 460 s (mypy cache warm; the suite and the sets run whole) | 460 s — unchanged by design: the local run already had its caches; the floor is the suite with coverage (182 s) and the sets (43 s) |
| `make test-fast`, unit tree, no failures / after one failure | — | 87 s (508 unit tests, no coverage, first run) / the failed tests first, stop at the first |
| `make evals-affected`, a docs-only change / one capability | — | no set runs / that capability's sets |

What the numbers say: the warm image saves the environment build (≈ 240 s against the cold baseline, 23 %); the rest of a local `make ci` is the gate itself run through the Windows bind mount, where the suite alone takes 288 s against 182 s natively and 70 s on the hosted Linux runner — the machine, not the pipeline. The stamp is the larger saving: a push after a green run costs one second instead of a second 13–17 minute run.

The check list of `make verify` is unchanged: `lint · api-check · ledgers-check · test · coverage-check · storage · evals · budgets-check · security · selftest`, the same 45 gate checks (`git diff main -- Makefile` touches only `ci`, the new targets and `verify-fast`).

Where the local time goes on an unchanged tree (this machine, Windows): lint 43 s (mypy incremental; 84 s cold), api-check 8 s, test 184 s (pytest with branch coverage; 80 s without coverage — coverage is the gate's floor, not optional), storage 15 s, evals 43 s for the twelve sets, security 22 s, selftest 4 s. The eval sets do not dominate, so they are not parallelised and `pytest-xdist` is not a dependency: measured on the suite, `-n 4` moved 184 s to 177 s wall — the long poles (the child-process parses, the storage container) are serial — so the register row was not worth its reason.

Stamp transcripts:
```
$ make stamp-check
stamp: tree 0a7b7366078d green in python:3.12.14-slim at 2026-09-21T14:01:34+00:00
exit 0
$ echo >> README.md; make stamp-check
stamp: the tree changed since its last green run
make: *** [makefile:103: stamp-check] Error 1
exit 2
$ git checkout -- README.md; make stamp-check
stamp: tree 0a7b7366078d green in python:3.12.14-slim at 2026-09-21T14:01:34+00:00
exit 0
```

## Decisions and questions
- F-019: the host's and the container's mypy runs shared `.mypy_cache` on the mounted tree and corrupted its sqlite store when both ran at once — the container's caches now live in their own volume, never on the tree.
- F-020: the first timing run showed the stamp test, run inside the image, inheriting `GIT_DIR` / `GIT_WORK_TREE` re-initialising the real repository (`core.filemode=true` and `core.worktree=/work` in its config, under which every mounted file reads as modified) and staging the real tree into the real index (the pre-commit hook refused the commit it attempted; `git reset` and two config lines undone by hand restored it, no content moved) — the fixture clears the git environment; the timings below are from the re-run.
- none new otherwise; the push rule's text mirrors the backend's.

## Commit
1. Files: `Makefile`, `.githooks/pre-push`, `tools/stamp.py`, `tools/affected.py`, `tools/evals.py`, `tests/unit/tools/**`, `docs/02-rules/RULE-005-git-and-sessions.md`, `docs/02-rules/RULE-006-enforcement.md`, `brain/**`
   Proposed: `build: warm ci caches, a run-once stamp for the push, iteration targets`
Green light: awaited

## Next
The assistant card.
