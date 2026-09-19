---
id: RULE-001
title: Code quality — budgets, comments, naming, hygiene, DRY
status: Binding
version: 1.0.0
owner: AI service lead
created: 2026-09-18
---

# RULE-001 — Code quality

Reused from a sibling Python service's rule page where the reason holds; tightened where this
service is stricter. Each reuse and each tightening is named in the row that carries it.

## §1 The rule of two — and where the second copy goes

Anything used twice is extracted, and the extraction follows **ownership**, never a grab-bag.
There is no `common/`, `utils/`, `shared/` or `helpers/`; the reusable home is always a named
package with one responsibility.

| Reused thing | Second use inside one capability | Second use across capabilities |
| --- | --- | --- |
| Value, literal, number | A named constant in that module or the capability's `descriptor.py` | `platform/<capability>` that owns the meaning (`platform/errors` codes, `platform/budgets` defaults) |
| Function | A function in the same module or a sibling module of the capability | A `platform/<name>` or `retrieval/<name>` package designed for it, with a name and a docstring; never `platform/util` |
| pydantic model | The capability's `schema.py` | `contract/envelopes.py` if the backend sees it; `platform/<name>` if it is infrastructure (ids, usage, provenance) |
| Prompt segment | A named section of the capability's prompt file | Never: prompts are per capability; a shared instruction is a `Q-NNN` |
| Grader | `evals/<name>/graders.py` | `evals/graders/<name>.py`, a named grader package |
| Query | — | A typed function in `platform/storage/queries/` |
| Test fixture or double | `tests/unit/<path>/conftest.py` | `tests/conftest.py` or `tests/fixtures/` |
| Check logic | — | `tools/checks/<name>.py`; the vocabulary in `tools/rules.py` |

Across capabilities DRY applies to the **contract** and the **kernel** — never to pipelines; two
capabilities with similar stages keep their own until a third needs the shape and a platform
package is designed for it. A `platform` package that exists only to de-duplicate two
capabilities and holds a product noun is a violation (`ARCH-011 §2`).

Enforced by `tools/checks/dupl` (duplicate blocks of 6 or more statements across
`capabilities/`, `providers/` and `retrieval/`, after normalising names — tightened from the
sibling's absence of any duplication check) and by `ruff` `PLR2004` (a bare number outside
0, 1, 2 becomes a constant). Magic values are banned: every number or string with meaning is a
constant whose name states its unit and reason — `MAX_INPUT_CHARS`, `CACHE_TTL_SECONDS`,
`REPAIR_ATTEMPTS`.

## §2 Budgets — CI-enforced, no override

| Budget | Limit | Counted how | Versus the sibling |
| --- | --- | --- | --- |
| File | **≤ 300 logical lines** | non-blank, non-docstring, non-comment lines; generated files exempt | tightened from 500 — matching the backend |
| Function | ≤ 50 lines | `tools/checks/funcbudget` | same |
| Statements per function | ≤ 40 | `ruff` `PLR0915` (`max-statements = 40`) | added |
| Cyclomatic complexity | ≤ 10 | `ruff` `C901` | same |
| Parameters | ≤ 5 — beyond that, a model | `ruff` `PLR0913` | same |
| Branches | ≤ 10 | `ruff` `PLR0912` | same |
| Returns | ≤ 3 | `ruff` `PLR0911` | added |
| Nesting | ≤ 3 (return early) | `ruff` `PLR1702` | added |
| Package cohesion | one capability per package; one responsibility per platform package; over ten files reported | `tools/checks/structure` (report) | replaces the sibling's directory cap of 12 |
| Route function | ≤ 6 statements: build the request, call `run`, return; no branch on content | `tools/checks/routes` | added |
| Test placement | `tests/unit/` mirrors `src/`; fixtures under `tests/fixtures/`; architecture and contract under their folders | `tools/checks/structure` | same idea |

Hitting a budget is a design signal: split by responsibility, never shuffle lines to satisfy the
counter. `pipeline_1.py` and `pipeline_2.py` are rejected; `pipeline.py`, `assemble.py`,
`postprocess.py` is the shape.

## §3 Comments

Code carries no narration. The **only** comments permitted in a `.py` file:

1. A **docstring on a public surface** — a module, a public class, a public function — one line
   stating the contract a caller relies on (`ruff` `D` with `pep257`; `D1xx` waived in tests and
   `tools/checks/`).
2. A **tool directive** with its reason on the same line: `# noqa: ANN401 — <reason>`,
   `# type: ignore[<code>]  # <reason>`, `# pragma: no cover — <reason>`. Reasons come from the
   allowlist in `tools/rules.py`; directives are counted by `tools/checks/comments` and the count
   may only fall.

Everything else — a "why", a "what", a TODO, commented-out code (`ERA`), a section banner, a
history note — is rejected. Rationale lives in an ADR, a decision, a finding, a test name or a
prompt file's header. If code needs a sentence to be understood, the code is not finished.

## §4 Naming

- Packages and modules: short lowercase singular nouns (`cache`, `budgets` when the noun is the
  set), never a generic from the banned list (`ARCH-011 §3`), never a version or a mood
  (`v2`, `new`, `final`, `temp`).
- Files: `snake_case.py`, one concept per file, the concept in the name. Prompts `prompt_vN.md`.
- Identifiers: PEP 8; booleans read as assertions (`is_cache_hit`, `can_stream`); constants
  `UPPER_SNAKE`; errors `SomethingError`; protocols named for the capability (`Provider`,
  `Storage`, `Clock`), never `IProvider` or `ProviderInterface`.
- Suffixes that say nothing (`Impl`, `Service`, `Manager`, `Helper`, `Util`, `Handler`) are
  rejected by `tools/checks/naming`.
- Capability names are `kebab-case` in the contract and the ledger (`improve-story`),
  `snake_case` as packages (`improve_story`); the descriptor carries both and
  `tools/checks/naming` verifies they agree.

## §5 Hygiene

No dead code, no unused imports or variables (`ruff` `F`, `ERA`); no `print` (`T20`); no
`eval`, `exec`, `shell=True`, `pickle` on inputs (`S`); no global mutable state (a module-level
`list`, `dict` or `set` that is mutated fails `tools/checks/globals`); no `import *`; no
notebook in the tree (`tools/checks/structure`); no reflection outside `config/` and
`tools/`; no third-party type in `contract/` or in the port's models beyond pydantic; every
dependency has a register row (`ADR-003 §3`, `tools/checks/deps`); licences allowlisted.
