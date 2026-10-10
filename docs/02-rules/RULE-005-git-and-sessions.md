---
id: RULE-005
title: Git, sessions and the brain
status: Binding
version: 1.4.0
owner: AI service lead
created: 2026-09-18
---

# RULE-005 — Git, sessions and the brain

## §1 Branches, hooks and the push precondition

- Trunk-based, and **there is no pull-request flow** (`D-041`). `main` is the only branch, and
  the only one ever pushed; `.githooks/pre-push` refuses any other ref. A contributor works on
  `main` itself, commits a finished slice, and pushes it in seconds (`D-069`): `git add <files>`
  (never `-A`), `git commit` (the pre-commit hook), `git pull --rebase` when `main` moved, then
  the push of `main` (the pre-push hook). Before the commit the contributor runs the tests of
  what changed — the touched packages, the touched capability's eval set when a capability
  changed — and nothing more; `make verify` and `make ci` are never a precondition. The hosted
  workflow runs on `main` after the push and nobody waits for it: a red push run is the
  contributor's next commit, ahead of feature work, and a red night is the morning's first.
  Force-push, history rewriting of anything pushed, and `--no-verify` are banned.
- A change is one task in one commit with a one-line subject (the lockfile, the rendered
  document and recorded fixtures go in their own `gen:` commit). There is no total of lines per commit; each file keeps its own budget
  (`tools/checks/filebudget`, `funcbudget`). `tools/checks/commitsize` holds it at commit: one
  ticket across the staged records' `**Ticket:**` fields, the message one subject line and
  nothing after it, a `gen:` commit generated paths only; there is no flag (`D-067`).
- Conventional Commits: `type(scope): imperative summary`, ≤ 80 characters, `scope` the
  capability or package (`feat(improve-story): pipeline v2 with comments context`). Types:
  `feat`, `fix`, `refactor`, `perf`, `test`, `eval`, `prompt`, `docs`, `build`, `ci`, `chore`,
  `gen` (rendered document, lockfile, fixtures only). `commit-msg` enforces it.
- **A commit and its push take seconds; the gate runs after the push** (`D-069`). The pre-commit
  hook checks the staged set, the pre-push hook admits `main` and scans the pushed range for
  secrets, and neither runs a pipeline, a container or a stamp. Per push, the hosted `ci.yml`
  runs `make verify-push` inside a budget of ten minutes, and a newer push cancels the run it
  supersedes; every night, `nightly.yml` runs the evals with their budgets, the drills, the
  storage suite repeated, the fuzz properties, the load run and the image scan. The workflow file
  holds only checkout, setup, `make tools`, `make hooks`, `make verify-push`
  (`tools/checks/ci`). `make ci`, `make ci-aware` and `make stamp-check` stay as tools a
  contributor may run for the whole answer locally; no hook calls them.
- **One door to the database.** `.github/workflows/` holds `ci.yml`, the nightly, the image
  workflow and the release workflow, each on its own row. Its trigger (a push to `main`), its container, its one service and its env equal what
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
  no Node toolchain in a Python repository): `pre-commit` runs `make verify-fast`
  (`tools/precommit.py`, on the staged set: format and lint on the staged Python files, the ⚡
  checks — the per-file ones on the staged files, a cross-file one on the whole repository when a
  staged file is one it reads — and gitleaks on the staged tree; a change to a shared
  configuration, a rule, the lockfile, the hooks or a check's own code, or a commit with nothing
  staged, formats and lints every file and runs every cross-file check (`tools/scope.py`, `D-066`,
  `D-070`); no type check, test or eval, which run on the hosted runner);
  `commit-msg` runs the message check; `pre-push` refuses every ref but `main` and runs gitleaks
  on the pushed range. A red hook blocks. `make test-fast` (the unit tree, last failures first,
  no coverage) and `make evals-affected` exist for iteration.
- **The repository speaks of "the lead" and "a contributor" and of nothing behind them.** No
  id of the lead's private planning, no name of its files and no name of its people is written
  anywhere in the tree — records, ledgers, code, fixtures, commit lines alike.
  `tools/checks/vocabulary` refuses the shapes (assembled at run time, so they never sit in the
  tree) in `verify-fast` and `verify`; a line that needs one of them is rewritten in the
  repository's own words.

## §2 Sessions and git

A working session finishes a slice, records it, and lands it.

1. The session works on `main` in the repository's own checkout.
2. Before committing it runs the tests of what changed and names them in the record; when a
   capability was touched, its eval numbers too.
3. It stages exactly the files of the slice, commits with one Conventional Commit line and
   pushes `main` (§1). No trailer follows the line.
4. Generated artefacts — `uv.lock`, `api/openapi.yaml`, recorded fixtures, ledgers — are their
   own commit (`gen(...)`), never mixed with hand-written changes.
5. It never force-pushes and never rewrites pushed history.

## §3 Tickets

`AI-NNN` in `brain/01-STATUS.md`: title, capability or package, the pages it names, the
functions of the previous system it retires, acceptance evidence required, state (`todo` /
`doing` / `blocked` / `review` / `done`), and the session records that touched it. No work
exists without a ticket; a ticket is claimed before code is written.

## §4 Session records

`brain/sessions/<YYYY-MM>/NNN-<slug>.md` from `_TEMPLATE-session.md`, written before the session
ends: ticket, the impact matrix, what changed (files), the tests run (`## Tests run`), the eval
and budget numbers when a capability changed, decisions made or needed, findings filed, the commit
line, and the next action. A session without a record did not happen.

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
