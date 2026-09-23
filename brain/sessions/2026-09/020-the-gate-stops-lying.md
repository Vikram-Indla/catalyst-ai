# 020 — the gate stops lying

**Date:** 2026-09-23 · **Ticket:** AI-017 · **Capability or package:** tools (install, stamp, rules, ci_postgres, checks/ci, checks/images), Dockerfile, Dockerfile.ci, the workflow, compose, RULE-005, RULE-006 · **Author:** a contributor

Seven findings from a review of the pipeline, built in order, each red before its fix and green
after.

## Read
`RULE-005 §1–2`, `RULE-006 §3`, `ARCH-011`; `tools/install.py`, `tools/stamp.py`,
`tools/checks/ci.py`, the Makefile, the Dockerfile, the workflow, the compose file; the vendors'
checksum lists for gitleaks 8.30.1 and oasdiff 1.32.1.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-017
Capability:      none — tools/install, tools/stamp, tools/rules, tools/ci_postgres, tools/checks/{ci,images},
                 Dockerfile, Dockerfile.ci, .github/workflows, docker-compose.yml, RULE-005, RULE-006
Inputs:          none
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged (every set re-run through the new database door; numbers unchanged)
Budget:          unchanged
Failure mode:    the gate's own: a tool that is not the pinned tool, a stamp for a tree that did not run,
                 an image that is not the one the stamp names, a hosted job that differs from the local one
Cache:           .tools/archives (verified archives, per platform)
Safety:          the gate's supply chain — a planted binary, a tampered download; the Docker socket leaves the pipeline
Contract:        unchanged
Invariants:      INV-061, INV-062, INV-063 (new)
Blast radius:    SYSTEM — every gate run, local and hosted
Decision level:  2
ADR:             none
```

## Finding 1 — `make tools` trusted HTTPS and nothing else
No checksum for either binary. Any binary already in `.tools/bin` was trusted unread, and any
`gitleaks` on `PATH` whose `version` output *contained* the pinned string was accepted. The machine
this was written on has a package-manager `gitleaks` 8.30.1 on `PATH`, and the installer took it.

**Red** — `tests/unit/tools/test_install.py` on the unchanged installer, 5 failed:
```
E   AssertionError: accepted C:\...\shims\gitleaks.BAT              (a shim printing the version)
E   Failed: DID NOT RAISE <class 'RuntimeError'>                    (a download with the wrong digest)
E   AssertionError: assert b'planted binary' == b'genuine binary'   (a binary planted in .tools/bin)
E   Failed: DID NOT RAISE <class 'RuntimeError'>                    (a version with no pinned line)
E   assert 0 == 1                                                   (the PATH copy taken, nothing downloaded)
```
**Fix.** `tools/checksums.sha256` carries the vendors' lines for every archive the installer can
ask for. Four of them were confirmed by downloading and hashing here: the linux and windows x64
archives of both tools. The installer refuses a version with no line before any download. It
refuses a download that does not match and writes nothing. It keeps the verified archive in
`.tools/archives` and verifies it again on every run, extracts the binary again every run, and
never looks at `PATH`. oasdiff ships one universal darwin archive under another name, so darwin
refuses with the missing-pin message instead of fetching a URL that does not exist.
**Green.** 5 passed. A real `make tools` here downloaded, verified and extracted both tools. A
second run downloaded nothing, and `gitleaks.exe version` gave `8.30.1`. On linux, inside the
image: `gitleaks 8.30.1 -> .tools/bin/linux-x64/gitleaks`. `RULE-006 §3`, `INV-061`.

## Finding 2 — the stamp proved the wrong tree
`write` hashed the tree when `make ci` *ended*, so a file edited during the run was stamped as
proven. This mirrors the backend's `begin`/`write` shape: `begin` notes the tree in the
worktree's own git directory, and `write` stamps only if the tree at the end is the noted one.
**Red** — the test that is today's sequence (nothing noted, a file edited, `write`):
```
E   AssertionError: the edited tree was stamped as proven
```
The two tests that use `begin` failed with `invalid choice: 'begin'`.
**Fix.** `stamp begin` writes `ci-begin` under `git rev-parse --git-dir`. `write` reads it, removes
it, and returns nothing unless the tree still matches. The run stays green; only the stamp is
withheld. The Makefile's `ci` calls `begin` first.
**Green.** 10 stamp tests pass. In the final `make ci`, the stamp was written for the unchanged
tree against the digest image. `RULE-005 §1`, `INV-062`.

## Finding 3 — the law and the hook contradicted each other
`RULE-005 §1` said work lands by pull request once a remote exists. The remote exists, and
`.githooks/pre-push` refuses every ref but `main`. The lead's decision (`D-041`): the hook is
right, there is no pull-request flow, and the page is reworded. No code changes.
**Red** — the hook fed on stdin (nothing pushed), beside the page on `main`:
```
$ echo "refs/heads/fix/AI-017-x 0000 refs/heads/fix/AI-017-x 0000" | bash .githooks/pre-push
pre-push: only main is ever pushed (got refs/heads/fix/AI-017-x)        exit=1
$ git show main:docs/02-rules/RULE-005-git-and-sessions.md | sed -n 15p
  `<type>/AI-NNN-<slug>`, lives at most three days, and lands by pull request once a remote
```
**Fix.** `RULE-005` 1.3.0:
- `§1`: `main` is the only branch pushed. The lead commits after an explicit yes, on a tree with
  both gates green and pasted, then pushes `main`. The hosted run is evidence after the fact, and
  a red one is fixed forward. The size rule is per commit.
- `§2` steps 1 and 6 are reworded to match.
- `§6` is "Change risk classes".
- `RULE-006` and the invariants preamble lost their "pull request" and "(CI, on the PR)" wording.
  The first sweep missed the abbreviation, and finding 4 caught it.

**Green.** No page under `docs/` describes a pull-request flow.

## Finding 4 — the image was a tag, so parity was luck
Both `FROM` lines, `CI_IMAGE` and `container.image` named `python:3.12.14-slim`. The hosted job
could pull other bytes than the ones the stamp named. The digest was read twice
(`image inspect` RepoDigests, `buildx imagetools inspect`), and both gave the index
`sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9`, so arm64 resolves it too.
**Red** — the new `tools/checks/images` on the unchanged files: 4 violations (`Dockerfile` ×2,
`Makefile CI_IMAGE`, the workflow's container), each `is python:3.12.14-slim, not the pinned …@sha256:…`.
**Fix.** `tools/rules.py` holds `BASE_IMAGE` and `CI_IMAGE`, and all references name them. The
check refuses a tag, a missing reference or a doubled one; it is in the gate, and its selftest
plant is red. `catalyst-ai check` and the stamp both resolve the digest form. "The pin moves only
in a `build(ci)` commit" is written, not checked: the message check cannot see the diff, but the
`images` check makes any move all-or-nothing.
**Green.** `images` ok; `RULE-005 §1`, `RULE-006` row, `INV-063`.

## Finding 5 — two doors to PostgreSQL, and a check that saw neither
The hosted job used a `services:` database named `postgres`, reached through
`CATALYST_AI_EVAL_DATABASE_URL`. `make ci` mounted the host's Docker socket so that
testcontainers could start its own database. `tools/checks/ci` read only `run:`/`uses:` in one
file. **One door was possible:** `tools/ci_postgres up` starts the pinned `pgvector` image
(digest read twice: `sha256:cf134a76…8e6f`) under the alias `postgres`, with the workflow's env
and health options, on a network of its own. The job joins it with the same variable. `down`
removes both, green or red. The socket mount and `TESTCONTAINERS_RYUK_DISABLED` are gone, and
the testcontainers fallback outside the pipeline uses the same pinned image.
**Red** — `tests/unit/tools/test_ci_workflows.py` on the unchanged check, 5 failed:
```
E   AssertionError: a second workflow passed: []
E   AssertionError: a changed service image passed
E   AssertionError: a changed service environment passed
E   AssertionError: a second service passed
E   AssertionError: an extra job variable passed
```
**Fix.**
- The check walks `.github/workflows/`, allows only `ci.yml`, parses it, and holds the trigger
  (a push to `main`), container, services and env to `tools/rules.py`, with a per-file key
  allowlist.
- A malformed workflow is a violation, not a crash; a plant found that gap.
- The dead `pull_request:` trigger is gone.
- A test ties `ci_postgres.run_args()` and `job_args()` to the workflow's own `services:` and `env:`.

**Green.** The tools tests pass. By hand: `up` healthy, `postgres:5432 - accepting connections`,
nothing left after `down`. The first interim `make ci` went red at `invariants`, on this
ticket's own rows: they named test files, which the registry reads as architecture tests. The
host lint had stopped earlier, at `sessions`. The rows now name the tools. `RULE-005 §1`,
`RULE-006`, `ARCH-011` 1.0.2, the config ledger.

## Finding 6 — `docker compose up` could not serve at all
Worse than the card expected. **Red** — today's compose file, `-p cai-red up --build --wait`:
```
Did not find any relations.                                   (no migration ran)
ValueError: unknown type: public.vector                       (the API app's startup; the extension is a migration)
Application startup failed. Exiting.                          (the API app)   · the ops app stays up on 9091
{"status":"not_ready","checks":{"settings":true,"storage":false,"serving":true}}   · API port: 000
```
Under it sat a second defect: the runtime image carried no `db/migrations`, so even
`compose run ai migrate` had nothing to apply.
**Fix: a one-shot `migrate` service** rather than `make migrate` as a first step. `up` is then
correct by itself, the image that migrates is the image that serves (over the compose network,
not the host's code against `localhost:5433`), and it is the shape a deployment takes. The
runtime stage copies `db/migrations`. `migrate` runs the same image and env as `ai`, and `ai`
waits on `service_completed_successfully`. The database is the pinned digest.
`tests/unit/tools/test_compose.py` was 4 red on the old files.
**Green** — `-p cai-green`:
```
migrate exited Exited (0) · migrate: 4 applied 20260920100000_… 20260922100000_… 20260924100000_… 20260925100000_…
(7 rows) auth_nonces · embeddings_documents · embeddings_work_items · index_documents_documents · index_documents_work_items · jobs · schema_migrations
{"status":"ready","checks":{"settings":true,"storage":true,"serving":true}} · API port /readyz: 200 · startup errors: 0
second up: migrate: 0 applied
```
Both stacks were removed with `down -v`. `RULE-006 §3` gains the compose line. **`F-035`** is filed:
a failed API startup leaves the process running. `/readyz` says `not_ready`, but the process
should exit non-zero. That is outside this ticket.

## Finding 7 — the pipeline installed its own tools on every run
The setup step (`apt-get install make git curl ca-certificates`, `pip install uv`) lost DNS
twice before the gate ran. **Red** — `make ci`'s own `docker run` (from `make -n ci`) on an
`--internal` network: the job and its database reach each other, nothing reaches the
internet, and both images were already pulled:
```
W: Failed to fetch http://deb.debian.org/debian/dists/trixie/InRelease  Temporary failure resolving 'deb.debian.org'
E: Unable to locate package make
netcut: exit=100
```
**Fix, up to the line this ticket may cross.** `Dockerfile.ci` is the pinned base with the four
packages, `uv==0.12.16` and a system-wide `safe.directory`. `make ci-image` builds it (local id
`sha256:3801000e34b44e7e6f790787ba49885193c0005006bfd3e5ded3ea6d129d91e6`). `images` holds its
`FROM` and its `uv` to the pins, and a test plants both. A local id is not a registry digest,
and it moves on every rebuild because apt reads a moving index. No registry exists. So
`CI_IMAGE`, the workflow and `rules.py` stay on the base with the setup step, nothing is pushed,
and **`Q-018`** asks where the image lives. Wiring it into `make ci` alone would undo finding 5's
parity.
**Green on the local image, same cut network** (`make tools && make hooks && make verify`, 16m35s):
```
uv sync --frozen --group dev   Checked 72 packages in 13ms · tools from the verified archives, nothing downloaded
GATE GREEN (48 checks) · 835 passed · storage ........ · drills ok · all fifteen eval sets over their floors
uv run --frozen pip-audit ...  ConnectionError: HTTPSConnectionPool(host='pypi.org', port=443)   → exit=2
```
Predicted before the run: the image removes every *install*, but `pip-audit` must *look up* the
advisory service. The pass also relied on warm caches. A cold hosted runner still fetches the
locked packages and the two tool archives; baking those in makes the image depend on `uv.lock`,
and that belongs to the `Q-018` answer.

## Verify
```
$ make verify
GATE GREEN (48 checks)
oasdiff: no breaking change against main
TOTAL                                                            6782     25    838     21    99%
836 passed in 119.26s (0:01:59)
   recall_at_10           0.914  (floor 0.85)
   mrr                    0.787  (floor 0.7)
   tenant_isolation       1.000  (floor 1.0)
No known vulnerabilities found
2:34PM INF no leaks found
selftest: 50/50 checks red on their plant
VERIFY GREEN
exit=0 elapsed=323s
(on the host; the storage tests and the evals through a throwaway container of the pinned image)
```
```
$ make ci
uv run --frozen python -m tools.stamp begin
ci-postgres: catalyst-ai-ci-postgres healthy on catalyst-ai-ci as postgres
gitleaks 8.30.1 -> .tools/bin/linux-x64/gitleaks
GATE GREEN (48 checks)
oasdiff: no breaking change against main
TOTAL                                                            6782     25    838     21    99%
836 passed in 309.05s (0:05:09)
   recall_at_10           0.914  (floor 0.85)
   mrr                    0.787  (floor 0.7)
   tenant_isolation       1.000  (floor 1.0)
No known vulnerabilities found
9:54AM INF no leaks found
selftest: 50/50 checks red on their plant
VERIFY GREEN
uv run --frozen python -m tools.stamp write --image python:3.12.14-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9
stamp: tree de58ec79753b in python:3.12.14-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9 at 2026-09-23T09:54:33+00:00 -- green
exit=0 elapsed=1169s
(nothing named catalyst-ai-ci left in `docker ps -a` or `docker network ls` afterwards)
```

## Eval and budget numbers
No capability was touched. Every set was re-run through the new database door inside the
image, all over their floors; retrieval `search` v1 (146 cases) gave recall@10 0.914, MRR 0.787,
tenant isolation 1.000, the same as when recorded.

## Decisions and questions
- `D-041` recorded (the lead's decision): no pull-request flow; the hook is right, `RULE-005` is reworded.
- `F-035` filed: a failed API startup leaves the process running (finding 6).
- `Q-018` asked: where the prebuilt CI image lives (finding 7); no registry is chosen here.

## Commit
Seven commits, in this order. The ledger is its own `gen` commit (`RULE-005 §2`), and none is
over 400 hand-written lines:
1. `build(tools): verify every tool archive against a pinned SHA-256` — tools/install.py, tools/checksums.sha256, tests/unit/tools/test_install.py
2. `fix(tools): stamp only the tree a pipeline run began on` — tools/stamp.py, tests/unit/tools/test_stamp.py
3. `ci(images): pin every image by digest and gate the CI image build` — Dockerfile, Dockerfile.ci, tools/rules.py, tools/checks/images.py, tools/checks/gate.py, tools/checks/selftest/__init__.py, tests/unit/tools/test_images.py
4. `ci(workflow): one workflow, one database door for both pipeline runs` — .github/workflows/ci.yml, Makefile, tools/checks/ci.py, tools/ci_postgres.py, tools/evalkit.py, tests/storage/conftest.py, tests/unit/tools/test_ci_workflows.py
5. `build(compose): migrate before serving, with the image that serves` — docker-compose.yml, tests/unit/tools/test_compose.py
6. `docs(rules): the practised flow, the pins and the one database door` — docs/02-rules/RULE-005-git-and-sessions.md, docs/02-rules/RULE-006-enforcement.md, docs/01-architecture/ARCH-011-repository-layout.md, docs/04-ledgers/invariants.md, brain/02-DECISIONS.md, brain/03-FINDINGS.md, brain/04-OPEN-QUESTIONS.md, brain/sessions/2026-09/020-the-gate-stops-lying.md
7. `gen(ledgers): the eval database variable names the one door` — docs/04-ledgers/config.md

Green light: yes, given in advance of the gates, conditional on both being green.

## Next
The lead answers `Q-018`. Then a `build(ci)` change pins the pushed image's digest in
`CI_IMAGE`, the workflow and `rules.py`, and removes the setup step.
