# 024 — the pipeline installs nothing

**Date:** 2026-09-24 · **Ticket:** AI-022 · **Capability or package:** tools (ci_image, ci_steps, checks/images), `Dockerfile.ci`, the Makefile, `RULE-005 §1` · **Author:** a contributor

Every local `make ci` spent about half an hour in apt before an eight-minute gate, and twice the
line dropped and the gate never ran. The prebuilt image was stopped at "no registry" in session
020. A registry is not needed to stop the installs: the image is built once on the machine, named
by what defines it, and `make ci` runs in it.

## Read
`RULE-005 §1`, `RULE-006 §3`; `Dockerfile.ci`, the Makefile's `ci`, `ci-image` and `stamp-check`,
`tools/ci_steps.py`, `tools/stamp.py`, `tools/checks/images.py`, `.githooks/pre-push`.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-022
Capability:      none
Inputs:          none
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged
Budget:          unchanged
Failure mode:    a missing image refuses `make ci` with the command that builds it; a drift between
                 the image and the hosted setup step is red
Cache:           the uv volume, read offline by the local run
Safety:          the mirror is a build argument; apt checks the signed index and every package hash
Contract:        unchanged
Invariants:      INV-067 (new)
Blast radius:    SYSTEM — every local pipeline run
Decision level:  2
ADR:             none (D-045)
```

## Changed
- `tools/ci_image.py` — the image's name (`catalyst-ai-ci:` + the first 12 hex of `Dockerfile.ci`'s
  SHA-256), `require` (refuse with `make ci-image` when missing), `build` (timed; the mirror only
  as a build argument, only when the machine's environment names one).
- `Dockerfile.ci` — `ARG APT_MIRROR` with the upstream default; the build log prints the mirror
  used; only the main archive line is rewritten, so security updates still come from upstream.
- `Makefile` — `ci` requires the image, runs in it with the setup step left out and uv offline
  (`CI_UV_OFFLINE`, 0 in `ci-cold`), and stamps its local id; `ci-image` and `stamp-check` follow.
- `tools/ci_steps.py` — `--prebuilt` drops exactly the setup step.
- `tools/checks/images.py` — the hosted setup step and the image install the same packages and pin
  the same uv; the plant is red.
- `RULE-005` 1.3.1 (`§1`), `D-045`, `INV-067`; `Q-018` answered.

## Red first
```
$ make ci                     (no image built for this Dockerfile yet)
ci: the pipeline's image is not built on this machine; run `make ci-image` first (catalyst-ai-ci:d1a924c66060)

$ the job on today's tree, network cut (an --internal network; the database reachable, nothing else)
W: Failed to fetch http://deb.debian.org/debian/dists/trixie/InRelease  Temporary failure resolving 'deb.debian.org'
E: Unable to locate package make
netcut: image=python:3.12.14-slim@sha256:2f17… flag=none exit=100 elapsed=8s

$ the job in the new image, network cut, uv online (the first attempt)
error: Failed to build `catalyst-ai @ file:///work`
  cause: No solution found when resolving: `hatchling==1.28.0`
  cause: Failed to fetch: `https://pypi.org/simple/hatchling/` … Temporary failure in name resolution
```
The third is a finding of its own: with every package in the warm volume, `uv sync` still asked
PyPI's index for the build backend each time it rebuilt the project. So the answer to "is PyPI
fetched on each run" was yes, for that lookup. Offline resolution from pinned versions (the lock
and the exact `hatchling` pin) is the same bytes, so the local run now reads the volume offline.

## The image build, timed from inside Docker
```
ci-image: building catalyst-ai-ci:d1a924c66060 with this machine's mirror
#5 [2/4] RUN echo "apt mirror: …" && sed … && apt-get update && apt-get install -y --no-install-recommends make git curl ca-certificates …
#5 DONE 21.7s
#6 [3/4] RUN pip install --no-cache-dir uv==0.12.16
#6 DONE 11.9s
ci-image: exit 0 in 45 s (this machine's mirror)
```
No other container ran during the build. Before, the same packages took about 31 minutes of every
`make ci` (10.0 MB of lists in 11 m 27 s and 24.8 MB of packages in 19 m 22 s, measured by the
reviewer); today's `make ci` runs took 633 to 3 063 s end to end, most of it that step. The mirror
is under the five minutes the reviewer asked for, by a wide margin. The build is now once per
`Dockerfile.ci`, not once per run.

## Network cut, in the new image
The same `--internal` network, the image `catalyst-ai-ci:d1a924c66060`, the setup step left out,
uv offline:
```
Checked 72 packages in 5ms
GATE GREEN (49 checks)
oasdiff: no breaking change against main
TOTAL                                                            6802     25    842     21    99%
869 passed in 207.94s (0:03:27)
drill: the switch works              (summarize, improve-story)
EVALS GREEN
requests.exceptions.ConnectionError: HTTPSConnectionPool(host='pypi.org', port=443): … /pypi/annotated-doc/0.0.5/json
make: *** [Makefile:84: security] Error 1
```
Nothing was installed and nothing was downloaded: every step up to the security step is green
with no route out. The one call left is `pip-audit` asking PyPI's advisory service about each
locked package. That is a lookup the gate exists to make, not an install, and it cannot pass a
cut by design; the connected runs below make it.

## Verify
```
$ make verify
GATE GREEN (49 checks)
oasdiff: no breaking change against main
TOTAL                                                            6802     25    842     21    99%
869 passed in 116.11s (0:01:56)
   recall_at_10           0.914  (floor 0.85)
   mrr                    0.787  (floor 0.7)
   tenant_isolation       1.000  (floor 1.0)
EVALS GREEN
No known vulnerabilities found
INF no leaks found
selftest: 51/51 checks red on their plant
VERIFY GREEN
exit=0 elapsed=279s
```
```
$ make ci                     (in catalyst-ai-ci:d1a924c66060, the setup step left out, uv offline)
GATE GREEN (49 checks)
oasdiff: no breaking change against main
TOTAL                                                            6802     25    842     21    99%
869 passed in 179.99s (0:02:59)
   recall_at_10           0.914  (floor 0.85)
   mrr                    0.787  (floor 0.7)
   tenant_isolation       1.000  (floor 1.0)
EVALS GREEN
No known vulnerabilities found
INF no leaks found
selftest: 51/51 checks red on their plant
VERIFY GREEN
stamp: tree 44f78fd0a97d in catalyst-ai-ci:d1a924c66060 at 2026-09-23T22:07:23+00:00 -- green
exit=0 elapsed=529s
```
`make ci` took 529 s end to end with no package step; the same pipeline took 633 to 3 063 s on
the base image today. The push re-runs it once, because this record changed after the stamp.

## Decisions and questions
- `D-045` proposed; `INV-067` added; `Q-018` answered by the lead (a registry next to the repository; its own ticket).

## Commit
1. `build(ci): make ci runs in the image built on the machine, and installs nothing` — tools/ci_image.py, tools/ci_steps.py, tools/checks/images.py, tools/checks/selftest/__init__.py, Dockerfile.ci, Makefile, tests/unit/tools/test_ci_image.py, docs/02-rules/RULE-005-git-and-sessions.md, docs/04-ledgers/invariants.md, brain/01-STATUS.md, brain/02-DECISIONS.md, brain/04-OPEN-QUESTIONS.md, this record
Green light: yes, given in this session

## Next
The image in the registry, pulled by digest.
