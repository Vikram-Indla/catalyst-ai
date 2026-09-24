---
id: RULE-005
title: Git, sessions and the brain
status: Binding
version: 1.3.3
owner: AI service lead
created: 2026-09-18
---

# RULE-005 — Git, sessions and the brain

## §1 Branches, hooks and the push precondition

- Trunk-based, and **there is no pull-request flow** (`D-041`). `main` is always deployable and is
  the only branch that is ever pushed; `.githooks/pre-push` refuses any other ref. A change reaches
  `main` one way: a working session prepares it in a private working copy, `make verify` and
  `make ci` are green on that tree and pasted in the record, and the lead commits it to `main` by
  hand after an explicit yes (§2) and pushes `main`. The hosted workflow then runs the same job
  on `main` after the fact: it is evidence that the pushed tree is what the local pipeline
  proved, never the door a change goes through. A red hosted run is fixed forward on `main`
  with its own commit. Force-push, history rewriting of anything pushed, and `--no-verify` are
  banned.
- A change is one ticket, ≤ 400 changed hand-written lines per commit (the lockfile, the
  rendered document and recorded fixtures are committed separately and do not count), both
  gates green, read by the lead before the yes.
- Conventional Commits: `type(scope): imperative summary`, ≤ 80 characters, `scope` the
  capability or package (`feat(improve-story): pipeline v2 with comments context`). Types:
  `feat`, `fix`, `refactor`, `perf`, `test`, `eval`, `prompt`, `docs`, `build`, `ci`, `chore`,
  `gen` (rendered document, lockfile, fixtures only). `commit-msg` enforces it.
- **A push is preceded by a green pipeline run of that tree; the stamp proves the tree.** `make ci`
  notes the tree before the run (`tools/stamp begin`, in the worktree's own git directory), runs
  the CI job verbatim inside the CI image and, green, writes a stamp keyed by the hash of the
  working tree and the image digest (`tools/stamp`, in the common git directory) — only if the
  tree is still the one noted at the start; a tree edited during the run is not stamped. `pre-push`
  skips the run when the stamp matches the tree being pushed, the image, and is younger than a
  day, printing it; otherwise it runs `make ci-aware`. That compares the tree with the last full
  green one, file by file (a full run keeps its manifest as the base; a scoped run proves its own
  push and is never a base), and runs what the changed files oblige by the
  map in `tools/change_map.py`: every check, the selftest and the secret scan for pages; those plus
  lint, types and the tools' tests for a check; the full `make ci` for anything else, and whenever
  there is no usable base (none, another image, older than a day). A step is skipped only when its
  inputs are the same bytes as a green run's; `tools/checks/change_map` refuses a file without a
  class and a page a test reads filed as a page. The hosted workflow on `main` always runs
  everything. The workflow file holds only checkout, setup, `make tools`, `make hooks`,
  `make verify` (`tools/checks/ci`).
- **One workflow, one door to the database.** `.github/workflows/` holds `ci.yml` and nothing
  else. Its trigger (a push to `main`), its container, its one service and its env equal what
  `tools/rules.py` pins, and `tools/checks/ci` reads every file in the directory and all of
  those keys. The tests reach PostgreSQL the same way in both runs: the pinned `pgvector` image
  as a service named `postgres`, through `CATALYST_AI_EVAL_DATABASE_URL`. The hosted job declares
  it under `services:`; `make ci` starts it from the same values on its own network
  (`tools/ci_postgres`) and removes it afterwards, green or red. No Docker socket is mounted into
  the pipeline, and a throwaway container is only a local convenience outside it.
- **One image, pinned by digest, never by tag.** `tools/rules.py` holds the pin. The Dockerfile's
  `FROM` lines, the Makefile's `CI_IMAGE` and the workflow's `container.image` name it exactly,
  so the local pipeline and the hosted job run the same bytes and the stamp's image is the one
  that ran (`tools/checks/images`). The pin moves only in a `build(ci)` commit that changes it and
  every reference together. `Dockerfile.ci` builds the pipeline's own image on the same base, with
  the tools the hosted job installs in its setup step baked in, and `tools/checks/images` holds
  the two to the same packages and uv pin. `make ci` runs in that image, named
  `catalyst-ai-ci:<hash of Dockerfile.ci>` (`tools/ci_image`); if it is missing on the machine,
  `make ci` refuses and names `make ci-image`, so an image is never built inside a push. The
  local run leaves out the setup step and runs uv offline against its warm volume; `make
  ci-cold` runs online. Debian's mirror is a build argument whose default is upstream: a
  machine may pass a nearer one from its own environment, never from the repository, and it
  never changes the image's name. The hosted job keeps its setup step until the image has a
  registry. It gets one in two commits: a push to `main` that changes `Dockerfile.ci` runs
  `ci-image.yml`, which builds the image labelled with the file's hash, runs the gate inside it
  and only then pushes it and prints its digest (the job alone holds `packages: write`); the
  next `build(ci)` commit pins that digest and the hash it was built from, and
  `tools/checks/images` refuses a `Dockerfile.ci` that no longer hashes to the pin.
- Committed hooks in `.githooks/` (`make hooks` points `core.hooksPath` at them; git-native,
  no Node toolchain in a Python repository): `pre-commit` runs `make verify-fast` (format, lint,
  the ⚡ checks, the eval sets a change can move, gitleaks on the staged tree — iteration, never
  evidence); `commit-msg` runs the message check; `pre-push` consults the stamp, then runs
  `make ci` where Docker is available and otherwise the full `make verify`, printing that parity
  with the CI image is not proven. A red hook blocks. `make test-fast` (the unit tree, last
  failures first, no coverage) and `make evals-affected` exist for iteration; neither is evidence.
- **The repository speaks of "the lead" and "a contributor" and of nothing behind them.** No
  id of the lead's private planning, no name of its files and no name of its people is written
  anywhere in the tree — records, ledgers, code, fixtures, commit lines alike.
  `tools/checks/vocabulary` refuses the shapes (assembled at run time, so they never sit in the
  tree) in `verify-fast` and `verify`; a line that needs one of them is rewritten in the
  repository's own words.

## §2 Sessions and git — the hybrid rule

A working session prepares a change; the lead decides it enters history.

1. The session works in its own working copy, never in the checkout of `main`.
2. Before proposing a commit it runs `make verify` and `make ci` and pastes both in the record;
   when a capability was touched, the eval numbers too.
3. It lists the changed files (a plain list), proposes **one** Conventional Commit line, and
   **asks in chat**. It does not stage, commit or push while waiting.
4. On an explicit yes ("commit", "go ahead", "yes") the lead's hand stages exactly the listed
   files and commits with exactly the proposed line. Any other reply is a no.
5. Generated artefacts — `uv.lock`, `api/openapi.yaml`, recorded fixtures, ledgers — are their
   own commit (`gen(...)`), never mixed with hand-written changes: two proposals, two yeses.
6. Never pushes anything and never rewrites history; pushing `main` is the lead's hand alone.

A commit found in history without its green light in a session record is a `RULE-000 §3`
rejection and is reverted.

## §3 Tickets

`AI-NNN` in `brain/01-STATUS.md`: title, capability or package, the pages it names, the
functions of the previous system it retires, acceptance evidence required, state (`todo` /
`doing` / `blocked` / `review` / `done`), and the session records that touched it. No work
exists without a ticket; a ticket is claimed before code is written.

## §4 Session records

`brain/sessions/<YYYY-MM>/NNN-<slug>.md` from `_TEMPLATE-session.md`, written before the session
ends: ticket, the impact matrix, what changed (files), the pasted `make verify` and `make ci`,
the eval and budget numbers, decisions made or needed, findings filed, the commit line proposed
and whether it was accepted, and the next action. A session without a record did not happen.

## §5 The registers

| Register | File | Rule |
| --- | --- | --- |
| Decisions | `brain/02-DECISIONS.md` | `D-NNN` · date · by · decision · why. Append-only; a reversal is a new row naming the old one |
| Findings | `brain/03-FINDINGS.md` | `F-NNN` · where · observed · expected · proposal · state. Code-versus-docs, a wrong grader, an out-of-scope defect |
| Questions | `brain/04-OPEN-QUESTIONS.md` | `Q-NNN` · question · why it blocks · options · the answer becomes a `D-NNN`. Every product question lands here |
| Status | `brain/01-STATUS.md` | The living state: tickets, what is blocked, what is next. Rewritten, not appended |

## §6 Change risk classes

| Class | Touches | Blast radius | Review requirement |
| --- | --- | --- | --- |
| `LOW` | one capability's internals, no contract, no prompt, no threshold | `LOCAL`, `CAPABILITY` | both gates green; lead commits |
| `MEDIUM` | a prompt version, a grader, a new eval case, a chunking parameter, an additive contract field | `CAPABILITY`, `CONTRACT` | both gates green; lead reads the eval delta and the changelog |
| `HIGH` | a new capability, a new operation, a model alias change, a platform package, a migration | `CONTRACT`, `PLATFORM` | lead reviews the impact matrix and the `INV-` list line by line; contract evidence pasted |
| `CRITICAL` | the boundary, tenancy, data classes, the port, retention, a threshold lowered, a budget widened, anything in `RULE-000 §6` | `SYSTEM` | Level-3 process; deployed alone, behind the kill switch |

`tools/checks/prclass` derives the minimum class from the changed paths and the `INV-` rows
named in the impact matrix, and fails a branch whose highest record claim is lower (the name is
historical; there are no pull requests). A branch carrying several records, one per proposed
commit, is judged by the highest claim, since it lands as one push and is reviewed at that class;
each record keeps its own change's true radius, and `tools/checks/commitclass` holds it to that
at each commit, from the files staged with it; a record without a claim is red at both.
