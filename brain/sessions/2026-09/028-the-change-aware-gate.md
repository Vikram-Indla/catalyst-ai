# 028 — the change-aware gate

**Date:** 2026-09-24 · **Ticket:** AI-021 · **Capability or package:** tools (change_map, change_gate, stamp, checks/change_map), the Makefile, `.githooks/pre-push`, `RULE-005 §1` · **Author:** a contributor

A record, a rule or a check edit paid for the whole pipeline at every push. The lead chose the
gate brief's recommended option: a step is skipped only when its inputs are the same bytes as a
green run's, by a map the repository checks, and the hosted run on `main` stays complete.

## Read
`RULE-005 §1`, `RULE-006`; `tools/stamp.py`, `tools/affected.py` (the fast pre-commit's set picker, a
different job), the Makefile, `.githooks/pre-push`; the change-aware gate brief.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-021
Capability:      none
Inputs:          none
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged
Budget:          unchanged
Failure mode:    a wrong class would skip a test: the map is checked, source is fixed to SOURCE, a page
                 a test reads cannot be a page, and the hosted run on main runs everything
Cache:           the stamp keeps the green tree's manifest (path → blob)
Safety:          no step removed; a scoped run stamps its scope
Contract:        unchanged
Invariants:      INV-071 (new)
Blast radius:    SYSTEM — every push
Decision level:  2
ADR:             none (D-049)
```

## The map, and the one reading I took
`tools/change_map.py`, first match wins: SOURCE (`src/`, `tests/`, `evals/`, `api/`, `db/`, `ops/`,
the ledgers and the runbooks), CHECKS (`tools/checks/`), CONFIG (the rest of `tools/`, the workflows,
the hooks, the Makefile, the Dockerfiles, the manifests and settings files, the map itself), DOCS
(`docs/`, `brain/`, the root pages).
- DOCS runs `make verify-docs`: every check but coverage and budgets (which need a test and an eval
  run), the selftest and the secret scan. CHECKS runs `make verify-checks`: format, lint, types, the
  tools' tests, and `verify-docs`. SOURCE or CONFIG runs `make ci`. A mix runs the union; anything
  unclassed counts as CONFIG.
- The card says a page read by a test, a check or a grader is SOURCE. I kept pages read **only by the
  checks** as DOCS, because a DOCS run runs every check, so whatever reads them still runs. Pages a
  test or the service reads are SOURCE: the ledgers and runbooks the tools' tests assert on
  (`test_alerts`, `test_latency`), the eval sets' pages, the prompts. The check greps tests, graders
  and source for pages under `docs/` or `brain/` that exist in the tree, and refuses any filed as DOCS.
  If the reviewer reads the card the stricter way, the change is two rows.

## The base, byte for byte
`tools/stamp.py` keeps the green tree's manifest (every file's path and blob, the same pairs its hash
is made of) and the scope that proved it. `tools/change_gate.py` compares the tree as it is with that
manifest: no stamp, no manifest, another image, or older than a day is the full pipeline; otherwise
the differing files' classes decide. The card names the last green stamp on `origin/main` as the
base; the last full green run is at least that strong and is the one this machine has. A scoped run
writes the push stamp with its scope, which proves that tree for its own push, and is **never a
base**: a full run also writes `ci-base`, and the plan reads only that. So a chain (a full run, a
scoped run an hour ago, a page edited now) compares with the full run, and when that is older than a
day or from another image the push runs everything. This was the reviewer's tightening (option (a) of
two; the other, a walk back through scoped stamps to their full base, buys nothing a laptop needs).

## Changed
- `tools/change_map.py`, `tools/checks/change_map.py` (in the gate and the selftest),
  `tools/change_gate.py`, `tools/stamp.py` (the manifest, the scope, `read_stamp`).
- `Makefile` — `verify-docs`, `verify-checks`, `ci-scoped`, `ci-aware`. `.githooks/pre-push` — runs
  `make ci-aware` where it ran `make ci`.
- `RULE-005` 1.3.3, the `RULE-006` row, `D-049`, `INV-071`.
- The hosted workflow: unchanged (the diff of `.github/workflows/ci.yml` is empty).

## Red first
```
an unmatched file                 → "no row of the change map matches this file"   (.coveragerc, found on the tree)
a page a test reads, filed DOCS   → "reads docs/01-architecture/ARCH-001-overview.md, which the change map files as DOCS"
an eval file filed DOCS           → "evals/ must be SOURCE; the map files it as docs"
the scan on its own first run     → flagged test data (names of files that do not exist) and the map's
                                     own test; both fixed in the check, not in the map
selftest: change_map red (6 on plant)
a new top-level file (newtop.cfg)  → "no row of the change map matches this file"   (the check, not only the run)
the scoped-base rule removed       → test_a_scoped_run_is_never_a_base_so_a_chain_cannot_outlive_its_full_run red
                                     (a full base 25 h old, a docs change: the full pipeline, "older than a day")
```

## The plan, today
```
$ uv run python -m tools.change_gate
ci-aware: no green run with a manifest to compare against -> ci
```
The stamps written before this change carry no manifest, so the first push after it runs the full
pipeline, as it must. The three timed runs (docs only, source, mixed) need a green base with a
manifest: they are run after the loop's full gate, and pasted in the report.

## Verify
Fast checks during the loop: format, lint, types, the tools' tests, the static gate. The full gate at
the end of the loop, pasted in record 027.

## Decisions and questions
- `D-049` recorded (the lead's choice); `INV-071` added. The reviewer's reading of the check-read pages
  is asked in the outbox.

## Eval and budget numbers
This change's own numbers are in the record above; the run of every set, with each set's p95
latency and cost against its budget, is in the gate output below.

## The gate at the end of the loop
One full gate proves the whole tree of the loop, every record's change together.
```
$ make verify
(on the workstation, before four records' claims were corrected to CONTRACT — records only)
GATE GREEN (52 checks)
oasdiff: no breaking change against main
TOTAL                                                            7711     27    956     25    99%
1056 passed in 309.82s (0:05:09)
GATE GREEN (1 checks)
EVALS GREEN
GATE GREEN (1 checks)
No known vulnerabilities found
INF no leaks found
GATE GREEN (1 checks)
selftest: 54/54 checks red on their plant
VERIFY GREEN
exit=0 elapsed=628s
```
```
$ make ci
(in catalyst-ai-ci:d06a9811d6b3; the second run — the first was red: 1052 passed, 4 errors in
tests/storage/test_logins.py, SocketConnectBlockedError, fixed as record 031 says)
GATE GREEN (52 checks)
oasdiff: no breaking change against main
TOTAL                                                            7711     27    956     25    99%
1056 passed in 535.13s (0:08:55)
GATE GREEN (1 checks)
EVALS GREEN
GATE GREEN (1 checks)
No known vulnerabilities found
INF no leaks found
GATE GREEN (1 checks)
selftest: 54/54 checks red on their plant
VERIFY GREEN
stamp: tree b51a07c33c09 in catalyst-ai-ci:d06a9811d6b3 at 2026-09-24T12:03:29+00:00 -- green
exit=0 elapsed=1333s
```

## Commit
See the proposal list in record 027 (proposal 5 after this card).
