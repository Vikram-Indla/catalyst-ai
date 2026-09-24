# 035 — the class of a branch, and of each commit

**Date:** 2026-09-24 · **Ticket:** AI-021 · **Capability or package:** tools/checks (prclass, commitclass, the gate's lists, the selftest), `RULE-005 §6`, `RULE-006` · **Author:** a contributor

The end-of-loop gate could not stamp the loop's tree. `prclass` held every changed record to the
radius of the whole branch diff, which is right for one record per push and wrong for sixteen: an
honest LOCAL record was red because a different proposal touched platform code. The lead chose to
judge the branch by its highest claim, with the per-record truth moved to each commit, where the
record's own files are known (the delivery review's reading).

## Read
`RULE-005 §6`, `RULE-006`; `tools/checks/prclass.py`, `tools/checks/gitinfo.py`, the pre-commit
hook and `make verify-fast`; the delivery review of the change.

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
Failure mode:    a branch whose every claim is below its derived radius, a changed record with no
                 claim, or a committed record below its own commit's radius -> red
Cache:           unchanged
Safety:          no class can be understated: the push by its highest claim, each commit by its own
Contract:        unchanged
Invariants:      unchanged
Blast radius:    SYSTEM — how every push and every commit is classed for review
Decision level:  2
ADR:             none (D-057)
```

## What changed
- **`tools/checks/prclass`** (the full gate) judges the branch:
  - the highest claim among its changed records must reach the radius the whole diff derives;
  - a changed record that claims no radius is red, so one claim cannot stand for a silent rest.
- **`tools/checks/commitclass`** (new; in the full gate, the fast set and the selftest) judges
  each commit. When files are staged, as they are one proposal at a time under the pre-commit hook,
  every staged session record must claim a radius at least the one its staged files derive. With
  nothing staged it passes, since a full gate over the working tree is not a commit.
- `RULE-005 §6`, a new `RULE-006` row, `D-057`.

## Red first
```
the loop's tree under the old rule     -> 6 honest records red (claims LOCAL / CAPABILITY, branch PLATFORM)
every record below the derived radius  -> "the highest claim is CAPABILITY but the changed paths derive PLATFORM"
one record at the radius, others lower -> green (test_several_records_pass_when_the_highest_claim_covers_the_branch)
a changed record with no claim         -> "a changed record claims no blast radius"
a staged LOCAL record with a config file -> "claims LOCAL but the files committed with it derive PLATFORM"
the same record with only its own files  -> green
selftest: prclass red (2 on plant), commitclass red (1 on plant); 54/54
```

## Eval and budget numbers
No capability changed in this record; the run of every set is in the gate output below.

## The gate at the end of the loop
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
Proposal 1 in record 027: the gate that stamps the other proposals runs the new rule.
