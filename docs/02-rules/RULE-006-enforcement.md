---
id: RULE-006
title: Enforcement — every rule is a check
status: Binding
version: 1.2.0
owner: AI service lead
created: 2026-09-18
---

# RULE-006 — Enforcement

> A rule enforced by no check is a wish. A rule in `RULE-000..009` without a row here is a defect
> in the rule: make it checkable or delete it.

## §1 Adding a rule

1. Write it in the rule page. 2. Add its row below naming the check. 3. Implement the check in
`tools/checks/<name>.py` (Python, the same interpreter as the service; no other language in the
gate). 4. Plant a violation under `tools/checks/selftest/plants/<name>/` and prove the check
fails on it. A rule without step 4 is a tracked gap (`F-NNN`), and no new rule lands while a gap
for the same check is open.

## §2 The gate

`make verify` runs every row below in order and stops at the first failure. CI runs `make
verify` and nothing else; `tools/checks/ci` holds the workflow to that. `make ci` runs the CI
job itself inside its image and is the push precondition. `make verify-fast` is the ⚡ subset for
the pre-commit hook. The **Built in** column names the ticket that built the check; every check exists from the
scaffold and passes vacuously on an empty tree, and `selftest` proves each red on its plant.

| Rule | Check | Tool | Built in |
| --- | --- | --- | --- |
| Formatting (RULE-002 §1) ⚡ | `ruff format --check` diff empty | `ruff` | AI-002 |
| Lint: hygiene, security, prints, commented code, annotations, docstrings, async, datetimes (RULE-001 §5, RULE-002) ⚡ | zero findings | `ruff check` with the select list | AI-002 |
| Types (RULE-002 §2) ⚡ | zero errors | `mypy --strict` | AI-002 |
| mypy overrides only under adapters and parsers (RULE-002 §1) ⚡ | zero overrides elsewhere | `tools/checks/mypy_overrides` | AI-002 |
| Complexity, parameters, branches, returns, statements, nesting, magic values (RULE-001 §2) ⚡ | zero findings | `ruff` `C901`, `PLR0913`, `PLR0912`, `PLR0911`, `PLR0915`, `PLR1702`, `PLR2004` | AI-002 |
| File ≤ 300 logical lines (RULE-001 §2) ⚡ | zero files over | `tools/checks/filebudget` | AI-002 |
| Function ≤ 50 lines (RULE-001 §2) ⚡ | zero functions over | `tools/checks/funcbudget` | AI-002 |
| Layout, test placement, fixtures under `tests/fixtures/`, no notebook, one capability per package; package size reported (RULE-001 §2, ARCH-011) ⚡ | zero placement violations | `tools/checks/structure` | AI-002 |
| Comments: docstrings and directives only; directives with allowlisted reasons; count never grows (RULE-001 §3) ⚡ | zero non-permitted comment lines; count ≤ baseline | `tools/checks/comments` | AI-002 |
| Banned package, file and identifier names; capability names agree (RULE-001 §4, ARCH-011 §3) ⚡ | zero matches | `tools/checks/naming` | AI-002 |
| Duplicate blocks across pipelines, adapters and retrieval (RULE-001 §1) ⚡ | zero blocks ≥ 6 statements | `tools/checks/dupl` | AI-002 |
| No global mutable state (RULE-001 §5) ⚡ | zero mutated module-level containers | `tools/checks/globals` | AI-002 |
| Layers and independence of capabilities (ARCH-012 §1–2) | contracts kept | `import-linter` + `test_capabilities_are_independent` | AI-002 |
| Boundary: no product schema import, no product database config, no call to the backend (ARCH-002 §1–2) | zero violations | `test_no_product_schema_import`, `test_no_product_database_config`, `test_service_never_calls_backend` | AI-002 |
| Every request field classified; no `RESTRICTED` field in the contract (ARCH-002 §3) | zero violations | `tools/checks/classification` | AI-002 |
| A read-only capability imports no client, socket, writer or ingest path (ARCH-002 §1; the assistant's rule, INV-050) | zero violations in the packages `rules.READ_ONLY_CAPABILITIES` names | `tools/checks/readonly` | AI-010 |
| The service verifies and never signs: no signing primitive, no key generation, no cryptography import outside the key registry, no bearer or service token in the source (ARCH-009 §1, §5; INV-053) | zero violations under `src/` | `tools/checks/origin` | AI-015 |
| No id of the lead's private planning, no name of its files and no name of its people anywhere in the repository (RULE-005 §1) | zero lines carrying the shapes, in every text file | `tools/checks/vocabulary` | AI-015 |
| Routes thin: ≤ 6 statements, no branch on content (RULE-001 §2) | zero violations | `tools/checks/routes` | AI-002 |
| Typed boundary: no `dict[str, Any]`, `Any` or raw JSON in routes, pipeline surfaces or the port (RULE-003 §1, §3) | zero violations | `tools/checks/contract` + `tools/checks/ports` | AI-002 |
| Rendered document equals the committed one; every operation carries `x-capability`, versions, `x-error-codes`, an example (RULE-003 §1) | zero drift; zero missing | `tools/checks/openapi` (`make api && git diff --exit-code api/`) | AI-002 |
| No breaking contract change without a version (ARCH-004 §6) | zero breaking diffs vs `main` | `oasdiff breaking` | AI-002 |
| Changelog entry for every document change (RULE-003 §1) | diff of `api/` ⇒ diff of the changelog | `tools/checks/changelog` | AI-002 |
| Error codes: declared, catalogued, listed on the operation, raised somewhere (RULE-003 §2) | zero orphans in either direction | `tools/checks/errors` | AI-002 |
| No SDK exception escapes an adapter (RULE-002 §4) | zero | `tools/checks/errors` | AI-002 |
| Config only through `config/`; every variable declared with class and doc (RULE-003 §5) | zero `os.environ` elsewhere; ledger equals the class | `tools/checks/config` | AI-002 |
| Every capability has a descriptor, settings row, eval set, budget, kill switch (ARCH-003, RULE-009 §2) | zero missing | `tools/checks/capabilities` | AI-002 |
| No prompt string in code; every prompt file has its header; a released prompt is never edited (RULE-008 §1–2) | zero violations | `tools/checks/prompts` | AI-002 |
| Pipeline stages in order; the port called only in `call` (ARCH-003 §2) | zero violations | `tools/checks/pipeline` | AI-002 |
| No model id outside the register and the adapter's `models.py` (ARCH-005 §2) | zero literals | `tools/checks/models` | AI-002 |
| Providers reached only through the port; no `httpx` or SDK import in a capability (ARCH-005 §1) | zero | `test_providers_only_via_port` | AI-002 |
| No network in the suite; every provider call replays a fixture (RULE-004 §4) ⚡ | zero sockets; zero un-fixtured calls | `pytest-socket` in `conftest.py` + `tools/checks/network` | AI-002 |
| No content in logs, traces, metrics, errors (ARCH-010 §1) ⚡ | zero content-shaped keys in logging calls | `tools/checks/logs` | AI-002 |
| Tenancy: `organization_id` in every tenant query; RLS on every tenant table; cache key carries the organisation (ARCH-006 §1, ARCH-008 §3) | zero misses | `tools/checks/tenancy` + `test_every_tenant_table_has_rls` | AI-002 |
| SQL only in `platform/storage/queries/`; no `SELECT *` (ARCH-006 §1) | zero | `tools/checks/sql` | AI-002 |
| Migrations forward-only with a header; every FK indexed (ARCH-006) | zero warnings | `tools/checks/migrations` | AI-002 |
| Every IO has a deadline; no unheld task (RULE-002 §3) | zero | `tools/checks/deadlines`, `tools/checks/tasks` | AI-002 |
| No inline clock, id or randomness (RULE-002 §5) ⚡ | zero | `tools/checks/inline` | AI-002 |
| Interfaces only at substitution boundaries (ARCH-012 §3) | zero single-implementation protocols outside the seams list | `tools/checks/interfaces` | AI-002 |
| Every logic module has a test module (RULE-002 §6) | zero orphans | `tools/checks/tests` | AI-002 |
| No mocking framework in tests (RULE-004 §2) | zero `unittest.mock` imports outside `tools/` | `tools/checks/tests` | AI-002 |
| Coverage floors by layer: 100 / 95 / 90 / 80 / 90 overall (RULE-004 §1) | per-module floors by path class | `tools/checks/coverage` | AI-002 |
| Contract test per operation; every listed error code asserted; stream terminal frame (RULE-004 §3) | every operation has a contract test; every code asserted | `tools/checks/journeys` | AI-002 |
| Property test per parser and chunker (RULE-004 §2) | every module tagged `parser` has a `hypothesis` test | `tools/checks/fuzz` | AI-002 |
| Eval gate: every grader above its floor; thresholds never lowered without a `D-NNN`; `injection` tag non-empty (ARCH-007, RULE-008 §3) | green | `make evals` + `tools/checks/evals` | AI-002 |
| Budgets: p95 latency and cost under the descriptor; budgets never widened without a `D-NNN` (ARCH-008 §1) | green | `tools/checks/budgets` | AI-002 |
| Security: `pip-audit` on the exported lock, `gitleaks`, licences (ARCH-009 §5) ⚡ (gitleaks) | zero known vulnerabilities; zero secrets; allowlist only | `pip-audit`, `gitleaks`, `tools/checks/licenses` | AI-002 |
| Image scan: zero fixable HIGH/CRITICAL in the runtime image (ARCH-009 §5) | `make image-scan` green on the release candidate | `trivy` (`--ignore-unfixed`) | AI-002 |
| Dependencies justified (RULE-001 §5) | every entry in `pyproject.toml` is a register row | `tools/checks/deps` | AI-002 |
| Python version agrees across `.tool-versions`, `pyproject.toml`, the image (RULE-002 §1) | equal | `catalyst-ai check` | AI-002 |
| Commit message format (RULE-005 §1) ⚡ | Conventional Commit, ≤ 80 chars | `.githooks/commit-msg` | AI-002 |
| CI job equals the gate: the workflow holds only checkout, setup, `make tools`, `make hooks`, `make verify` (RULE-005 §1) | zero other steps | `tools/checks/ci` | AI-002 |
| Push preceded by a green pipeline run of that tree; the stamp proves the tree (RULE-005 §1) | a stamp for this tree and image, younger than a day, else `make ci` green | `.githooks/pre-push` · `tools/stamp` | AI-002, AI-012 |
| Generated artefacts committed separately (RULE-005 §2) | no commit mixes `uv.lock`, `api/`, fixtures with hand-written files | `tools/checks/commits` (CI, on the PR) | AI-002 |
| Session record carries the impact matrix, the gate output and the eval numbers (RULE-007) | present for every session that changed code | `tools/checks/sessions` (CI, on the PR) | AI-002 |
| PR risk class not understated (RULE-005 §6) | claimed ≥ derived | `tools/checks/prclass` | AI-002 |
| Kill switch per capability; deprecations carry replacement and sunset; nothing survives its sunset (RULE-009) | zero missing; zero overdue | `tools/checks/capabilities`, `tools/checks/deprecations` | AI-002 |
| Invariants registry: every row names an existing check; every architecture test is claimed (RULE-000 §6) | zero orphans | `tools/checks/invariants` | AI-002 |
| Every check fails on its planted violation (§1) | all plants red | `tools/checks/selftest` | AI-002 |

## §3 Commands

```
make tools        uv sync --frozen (dev group) · gitleaks and oasdiff pinned in .tool-versions into .tools/bin
make hooks        git config core.hooksPath .githooks
make fmt          ruff format
make lint         ruff format --check · ruff check · mypy --strict · import-linter · every tools/checks module but coverage
make coverage-check   the coverage floors, after make test wrote coverage.json
make lint-fast    the ⚡ subset of the above
make api          render api/openapi.yaml from the app
make api-check    the rendered document equals the committed one
make test         tests/architecture first, then pytest with coverage and the socket guard
make test-fast    the unit tree, last failures first, stop at the first, no coverage — iteration, never evidence
make storage      tests/storage against testcontainers once db/migrations has a file
make evals        every eval set against recorded fixtures once evals/ has a set
make evals-affected   the sets a change since main can move (tools/affected) — iteration, never evidence
make security     pip-audit on the exported lock · gitleaks · licences
make selftest     every check red on its plant, one line per check
make verify       lint · api-check · ledgers-check · test · coverage-check · storage · evals · security · selftest   (= CI)
make ci           the workflow's run steps verbatim, inside the CI image; green, it stamps the tree   (= pre-push)
make ci-cold      the same with the image's cache volumes dropped first (the cold number of the record)
make stamp-check  whether this tree, in this image, has a green run younger than a day (what pre-push asks)
make verify-fast  lint-fast · evals-affected · gitleaks on the staged tree                          (= pre-commit)
make image        build the runtime image · make image-scan: trivy on it (release candidate)
make check        catalyst-ai check: toolchain agreement and settings
make record · make new-capability   built with the first adapter and the golden capability
make serve · make worker · make migrate
```

Toolchain versions are pinned in `.tool-versions` and `uv.lock`; upgrading one is its own change.
`make ci` keeps uv's cache, the project environment and the ruff, mypy and hypothesis caches in
named volumes (`catalyst-ai-ci-*`), apart from the host's own caches so the two never share a
file; pytest's cache stays off in the gate (`pytest.ini`) and on only in `make test-fast`.
