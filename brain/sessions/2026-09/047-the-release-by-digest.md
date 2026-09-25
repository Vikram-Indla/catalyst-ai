# 047 — The release: built once, pushed, named after its commit, pointing the manifests at a digest

**Date:** 2026-09-24 · **Ticket:** AI-036 (4 of 4: the release) · **Capability or package:** `tools/release.py`, the Makefile (`release`), its tests · **Author:** a contributor

With the manifests in `deploy/` (record 046), a release needs the runtime image built once,
pushed, and a delivery-pipeline release that names it by digest, so no environment ever rebuilds.
This change adds that as a `make` target a workstation can run. The hosted job that runs it on each
push to `main` is not added yet: its authentication step could not be verified from here (below).

## Read
`gcloud deploy releases create` (the reference, checked on 2026-09-24: `RELEASE`,
`--delivery-pipeline`, `--region`, `--images=NAME=TAG`, `--source`, `--skaffold-file`,
`--deploy-parameters` — **verified**); the Cloud Deploy page on image placeholders (record 046);
the workflow allowlist (`tools/checks/ci.py`, `workflow_rows.py`: only `actions/checkout@v4` may be
used); `RULE-007 §2` (a new dependency is a stop condition).

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-036 (the release, 4 of 4)
Capability:      none — the release
Inputs:          RELEASE_REGISTRY, RELEASE_LOCATION from the environment; the checked-out commit
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged
Budget:          unchanged
Failure mode:    a missing setting, a partial commit id or a tag where a digest belongs: refused,
                 before anything is created
Cache:           none
Safety:          no location or registry in the repo; the caller's own login
Contract:        unchanged
Invariants:      unchanged
Blast radius:    LOCAL — tools and the Makefile
Decision level:  1
ADR:             none
```

## What changed
- **`make release`** (`tools/release.py`), each step printed before it runs; `--print` runs none:
  1. `docker build`, the image labelled `org.opencontainers.image.revision=<commit>`, tagged
     `<RELEASE_REGISTRY>/catalyst-ai:<commit>`;
  2. `docker push`;
  3. the registry's digest read back (`RepoDigests`) — anything but
     `<registry>/catalyst-ai@sha256:…` refuses the release;
  4. `gcloud deploy releases create catalyst-ai-<commit> --delivery-pipeline=catalyst-ai
     --region=<RELEASE_LOCATION> --source=deploy --skaffold-file=skaffold.yaml
     --images=catalyst-ai=<digest>`. The release waits for the lead's approval to roll out.
- The registry and the location are configuration, from the environment; missing either refuses
  with its name. The release is named after the full commit id (`catalyst-ai-<40 hex>`, 52
  characters; the name rules' limit is **unverified** here).

## Not added, and why: the hosted release job
The job would hold `id-token: write` alone and log in to the delivery project by workload identity
federation. Two paths, neither mine to choose:
- **Google's login action.** The allowlist holds only `actions/checkout@v4`; adding
  `google-github-actions/auth` is a new third-party dependency, a lead's decision.
- **No action.** Build the federation's credential file with `gcloud` from the job's OIDC token.
  The documentation page for deployment pipelines holds no such command to copy (asked for it
  verbatim: none). I will not write an unverified invocation into the release path.

Once one path is chosen, the job is three lines of steps (checkout, the login, `make release`)
plus its allowlist row. It is written up for the release owner in the outbox.

## Red first
```
the digest check removed
  test_a_tag_instead_of_a_digest_stops_the_release_before_it_is_created             FAILED
restored: 5 passed; the tools suite 143
make release --print, with the two settings: the four steps printed, nothing run
make release --print, without them: "RELEASE_REGISTRY, RELEASE_LOCATION must be set", exit 1
```

## Eval and budget numbers
No capability changed; no eval set moved.

## Verify
Fast checks in the loop: the tools suite, lint, types, the static gate. The full gate, on the tree
this change is committed from:
```
$ make verify
VERIFY GREEN — GATE GREEN (56 checks) · 1189 passed, coverage 99.41% · EVALS GREEN · selftest 58/58 (on the host, before record 043's make hooks fix)
$ make ci
VERIFY GREEN in catalyst-ai-ci:d06a9811d6b3 — 56 checks · 1189 passed, 99.41% · EVALS GREEN · selftest 58/58 · stamp: tree f777f5806cb3 at 2026-09-25T07:16:19+00:00 -- green
```

## Decisions and questions
- The hosted job's login: record 048.

## Commit
- `build(release): build once, push, and name the release after its commit`
