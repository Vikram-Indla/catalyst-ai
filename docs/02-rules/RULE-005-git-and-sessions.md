---
id: RULE-005
title: Git, sessions and the brain
status: Binding
version: 1.2.0
owner: AI service lead
created: 2026-09-18
---

# RULE-005 — Git, sessions and the brain

## §1 Branches, hooks and the push precondition

- Trunk-based. `main` is always deployable. Work happens on a short-lived branch named
  `<type>/AI-NNN-<slug>`, lives at most three days, and lands by pull request once a remote
  exists; until then the lead commits to local `main` and the same rules apply. Nobody pushes
  `main` directly from a working session; force-push, history rewriting of anything pushed, and
  `--no-verify` are banned.
- A pull request is one ticket, ≤ 400 changed hand-written lines (the lockfile, the rendered
  document and recorded fixtures are committed separately and do not count), CI green, reviewed
  by the lead.
- Conventional Commits: `type(scope): imperative summary`, ≤ 80 characters, `scope` the
  capability or package (`feat(improve-story): pipeline v2 with comments context`). Types:
  `feat`, `fix`, `refactor`, `perf`, `test`, `eval`, `prompt`, `docs`, `build`, `ci`, `chore`,
  `gen` (rendered document, lockfile, fixtures only). `commit-msg` enforces it.
- **A push is preceded by a green pipeline run of that tree; the stamp proves the tree.** `make ci`
  runs the CI job verbatim inside the CI image and, green, writes a stamp keyed by the hash of
  the working tree and the image digest (`tools/stamp`, in the common git directory). `pre-push`
  skips the run when the stamp matches the tree being pushed, the image, and is younger than a
  day, printing it; otherwise it runs. The workflow file holds only checkout, setup, `make tools`,
  `make hooks`, `make verify` (`tools/checks/ci`).
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

1. The session works on the ticket's branch, never on `main`.
2. Before proposing a commit it runs `make verify` and `make ci` and pastes both in the record;
   when a capability was touched, the eval numbers too.
3. It lists the changed files (a plain list), proposes **one** Conventional Commit line, and
   **asks in chat**. It does not stage, commit or push while waiting.
4. On an explicit yes ("commit", "go ahead", "yes") the lead's hand stages exactly the listed
   files and commits with exactly the proposed line. Any other reply is a no.
5. Generated artefacts — `uv.lock`, `api/openapi.yaml`, recorded fixtures, ledgers — are their
   own commit (`gen(...)`), never mixed with hand-written changes: two proposals, two yeses.
6. Never pushes `main`, never opens or merges a pull request, never rewrites history.

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

## §6 Pull-request risk classes

| Class | Touches | Blast radius | Review requirement |
| --- | --- | --- | --- |
| `LOW` | one capability's internals, no contract, no prompt, no threshold | `LOCAL`, `CAPABILITY` | CI green; lead merges |
| `MEDIUM` | a prompt version, a grader, a new eval case, a chunking parameter, an additive contract field | `CAPABILITY`, `CONTRACT` | CI green; lead reads the eval delta and the changelog |
| `HIGH` | a new capability, a new operation, a model alias change, a platform package, a migration | `CONTRACT`, `PLATFORM` | lead reviews the impact matrix and the `INV-` list line by line; contract evidence pasted |
| `CRITICAL` | the boundary, tenancy, data classes, the port, retention, a threshold lowered, a budget widened, anything in `RULE-000 §6` | `SYSTEM` | Level-3 process; deployed alone, behind the kill switch |

`tools/checks/prclass` derives the minimum class from the changed paths and the `INV-` rows
named in the impact matrix, and fails a request that claims a lower one.
