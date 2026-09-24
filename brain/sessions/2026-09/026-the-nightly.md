# 026 — the nightly

**Date:** 2026-09-24 · **Ticket:** AI-020 · **Capability or package:** `.github/workflows/nightly.yml`, tools/checks (ci, nightly_job, workflow_rows), the Makefile, the property tests' counts · **Author:** a contributor

A nightly on the hosted runner is extra evidence, never the push gate. It could not land while the
workflow check read a single file; the directory walk now reads every file against its own row, so
the nightly gets one.

## Read
`RULE-005 §1`, `RULE-006`; `tools/checks/ci.py`, the Makefile, `tests/conftest.py`, the five property
test files, `tools/load.py`.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-020
Capability:      none
Inputs:          none
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged
Budget:          unchanged
Failure mode:    a nightly red is read at the next start and filed as a finding the same day; it
                 never blocks a push
Cache:           none
Safety:          the nightly holds no secret and writes nothing but its log
Contract:        unchanged
Invariants:      INV-069 (new)
Blast radius:    LOCAL — a scheduled job and three make targets
Decision level:  1
ADR:             none (D-047)
```

## What the nightly runs, and why these
The gate already runs everything once per push. The nightly runs what a push cannot afford:
- **`make nightly-fuzz`** — the five property tests under the `nightly` Hypothesis profile: each
  test's own count times twenty (`tests/conftest.examples`), so the slow parsers stay
  proportionally smaller. `test_chunking_property` goes from 150 and 100 examples to 3 000 and 2 000.
- **`make nightly-repeat`** — the storage suite five times in a row (`REPEATS=` to change it). Two
  of today's findings were tests that depended on timing (`F-040`, `F-042`); a repeat is where the
  next one shows itself.
- **`make load N=64 ROUNDS=16`** — the concurrency test at four times the gate's width.

**Not the image scan.** `make image-scan` builds the runtime image and runs trivy on it. The nightly
runs in the same container as the gate, which has no Docker, and trivy is not one of the pinned
tools. It stays a release-candidate step, and it needs its own job and a pinned scanner first.
The eval sets are not repeated: on authored fixtures they are deterministic, so a repeat measures
nothing until recorded fixtures exist.

## Changed
- `.github/workflows/nightly.yml` — `schedule` (02:00 UTC) and `workflow_dispatch`; the same
  container, service and env as `ci.yml`; the pinned setup line, checkout, `make tools`,
  `make nightly`.
- `tools/checks/nightly_job.py`, `tools/checks/workflow_rows.py`, `tools/checks/ci.py` — the
  nightly's row (its triggers, the gate's job shape, `make` targets only); the step and job reading
  that every row shares now lives in one module, which the image workflow's row uses too.
- `Makefile` — `nightly`, `nightly-fuzz`, `nightly-repeat`.
- `tests/conftest.py` — the `nightly` profile and `examples()`; the property tests read their
  counts through it.
- `RULE-006` row, `D-047`, `INV-069`.

## Red first
```
an unlisted step in nightly.yml   → "the nightly runs \"python -c 'print(1)'\", which it may not"
                                     "the nightly does not run `make nightly`"
a nightly on every push           → "triggers are not {'schedule': …}"
another container shape           → "job key 'container' is …, not the pinned …"
selftest: ci red (11 on plant)
```

## Every nightly step, run here once
```
$ make nightly
uv run --frozen pytest tests/unit/retrieval/parsers tests/unit/retrieval/test_chunking_property.py -k property --hypothesis-profile=nightly
9 passed, 22 deselected in 45.00s
nightly-repeat: storage run 1 of 5 … storage run 5 of 5            (each green)
uv run --frozen python -m tools.load --concurrency 64 --rounds 16
  p50 1275 ms · p95 2337 ms · max 2660 ms · provider calls 2048 · budget refusals 0
  p50 450 ms · p95 699 ms · max 717 ms · provider calls 0 · budget refusals 64
load: every stream terminated and a spent tenant was refused
NIGHTLY GREEN
exit=0 elapsed=209s
```

## Hosted
The first hosted nightly runs after these changes reach `main`, which is after the loop; its run id
goes into the report then.

## Verify
Fast checks only during the loop (the lead's instruction): format, lint, types, the tools and
retrieval tests, the fast gate. The full gate runs once at the end of the loop, over every proposal.

## Decisions and questions
- `D-047` proposed; `INV-069` added.

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
See the proposal list in the last session record of the loop.
