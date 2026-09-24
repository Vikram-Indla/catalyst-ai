# 030 — the nightly image scan

**Date:** 2026-09-24 · **Ticket:** AI-027 · **Capability or package:** `.github/workflows/nightly.yml`, `tools/install.py`, `tools/checksums.sha256`, `tools/checks/nightly_job.py`, the Makefile · **Author:** a contributor

A nightly scan of the runtime image was promised (`D-005`, `RULE-006`). The nightly of record 026
runs in the gate's container, which has no Docker, so the scan was left out (`D-047`). It now has
a job of its own on the runner, with the scanner pinned like every other tool.

## Read
`RULE-006` (the image scan row), `D-005`, `D-045`, `D-047`; `tools/install.py`, the Makefile,
`tools/checks/nightly_job.py`, `tools/checks/workflow_rows.py`; the scanner's release checksum file.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-027
Capability:      none
Inputs:          none
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged
Budget:          unchanged
Failure mode:    a red scan never gates a push; it files a finding the same day
Cache:           the verified archive is kept in .tools/archives like the gate's tools
Safety:          the scanner is verified against the vendor's checksum; never a scanner action
Contract:        unchanged
Invariants:      unchanged (INV-069: the nightly is evidence, never the door)
Blast radius:    LOCAL — a scheduled job and a tool group nothing else reads
Decision level:  2
ADR:             none (D-051)
```

## What changed
- **The job.** `nightly.yml` gains `image-scan` on `ubuntu-latest`: checkout, `pip install
  uv==0.12.16` (the image workflow's setup line), `make tools`, `make scan-tools`, `make
  image-scan`, each runnable verbatim on a workstation. The nightly's row
  now holds two jobs. The scan job's shape is pinned, its steps must run in that order, and a
  scanner action (`uses:`) is refused like any action but checkout.
- **The scanner.** `trivy 0.72.0` was already in `.tool-versions`. Its five archives now have their
  lines in `tools/checksums.sha256`, copied from the vendor's checksum file, which was read twice and
  compared (identical, 2 120 bytes): `https://github.com/aquasecurity/trivy/releases/download/v0.72.0/trivy_0.72.0_checksums.txt`,
  read twice on 2026-09-24 in this session. A version bump repeats exactly that: two reads of the
  release's own checksum file, compared, before a line is copied. `tools/install.py` builds the vendor's archive names
  (`trivy_<v>_Linux-64bit.tar.gz`, `…_windows-64bit.zip`, and so on).
- **A group of its own.** `make scan-tools` (`python -m tools.install --scan`) installs the
  scanner; `make tools` installs only the gate's tools. The card named `make tools`, but the gate
  never needs the scanner. Pulling its archive into every `make ci` would bring back the network
  dependency `D-045` removed. The verification is the same code path.
- **The database date.** `make image-scan` runs the scan, then `trivy version`, which prints the
  vulnerability database's version and date, and then exits with the scan's status.
- `RULE-006` (the image scan row and the workflow row), the runbooks index (what a red night means),
  `D-051`.

## Red first
```
a scanner action in place of `make image-scan` → "the nightly uses aquasecurity/trivy-action@master, which it may not"
                                                 + "the scan job must set up, then run tools, scan-tools and image-scan, in order"
the scan job renamed                           → "the nightly must hold the 'image-scan' job"
make scan-tools and make image-scan swapped    → "the scan job must set up, …, in order"
a download whose digest is not the pinned one  → refused, nothing lands (the installer's existing test, the same path for every tool)
```

## The local scan (after the lead approved the download)
```
$ make scan-tools
downloading https://github.com/aquasecurity/trivy/releases/download/v0.72.0/trivy_0.72.0_windows-64bit.zip
trivy 0.72.0 -> .tools/bin/windows-x64/trivy.exe          (the archive matched its pinned line)
$ make image-scan                                          (the runtime image rebuilt from cache)
[vulndb] Downloading vulnerability DB...  repo="mirror.gcr.io/aquasec/trivy-db:2"
Detected OS  family="debian" version="13.7"   pkg_num=87
catalyst-ai:local (debian 13.7)   debian       0
28 Python packages               python-pkg   0 each
Version: 0.72.0
Vulnerability DB:
  Version: 2
  UpdatedAt: 2026-09-24 06:44:41 UTC
  NextUpdate: 2026-09-25 06:44:41 UTC
exit=0
```
Zero fixable HIGH or CRITICAL findings in the runtime image on the database of 2026-09-24 06:44
UTC, and the run printed that date, as the acceptance line asks.

## Verify
Fast checks during the loop: the workflow check, the tools' tests, lint and types. The full gate at
the end of the loop is pasted in record 027.

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
See the proposal list in record 027.
