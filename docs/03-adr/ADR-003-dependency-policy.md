---
id: ADR-003
title: Standard library first; no orchestration framework; every dependency justified here
status: Accepted
date: 2026-09-18
deciders: AI service lead
supersedes: —
superseded_by: —
level: 2
---

# ADR-003 — Dependency policy and the register

## Context

Python's ecosystem offers a framework for every stage of a model pipeline, and most hide the
provider call, the prompt, or both, behind an abstraction that changes every quarter. A test
that cannot see the provider call cannot record it; a prompt inside a framework's template
cannot be versioned as a file; a chain that retries on its own defeats the adapter's budget.
The standard library covers logging, JSON, hashing, `asyncio`, subprocesses and `unittest`-free
testing with `pytest`; what it lacks is listed below with the reason.

## Decision

The standard library first. A library is added only where the standard library has a gap, is
called by our code (never calls our code back through a lifecycle), never appears in a contract
model or the port, and has a row in §3 with its reason and the alternative rejected.
`tools/checks/deps` fails a `pyproject.toml` entry without a row; `tools/checks/licenses`
fails a licence outside the allowlist (MIT, BSD, Apache-2.0, PSF, ISC, MPL-2.0).

## §3 The dependency register

| Package | Reason | Alternative rejected |
| --- | --- | --- |
| `fastapi` | the contract surface; renders pydantic models to OpenAPI 3.1; async-native | `flask` (no async, no schema), `litestar` (smaller ecosystem for the same shape) |
| `uvicorn` | the ASGI server | `hypercorn` (no advantage here) |
| `starlette` | the ASGI toolkit under FastAPI, pinned directly because FastAPI's floor sits below the audited version; `pip-audit` decides the pin | letting FastAPI choose (an unaudited transitive) |
| `pydantic` (v2) | every boundary model, validation, JSON schema | `msgspec` (faster, no OpenAPI integration), dataclasses (no validation) |
| `pydantic-settings` | the typed settings object from the environment | hand-rolled `os.environ` parsing |
| `httpx` | every outbound HTTP call; async; a pluggable transport that makes recording possible | `aiohttp` (no transport seam for replay), provider SDKs alone (hide the wire) |
| `asyncpg`, `asyncpg-stubs` (dev) | the PostgreSQL driver; async; typed parameters; the stubs for `mypy --strict` | `psycopg` (fine; one driver only), any ORM (banned) |
| `pgvector` (Python) | the vector type codec for `asyncpg` (brings `numpy`); no `py.typed` → the contained `ignore_missing_imports` under `platform/storage`, the database adapter | hand-rolled encoding |
| `opentelemetry-api`, `-sdk`, `-instrumentation-fastapi`, `-instrumentation-httpx` | traces and metrics, the standard | vendor SDKs |
| `tiktoken` or the provider's tokeniser (adapter-local) | token counting for budgets before a call | estimating by characters |
| `python-docx`, `python-pptx`, `pypdf` (adapter-local under `retrieval/parsers`) | document parsing for ingest; no `py.typed` → the contained `ignore_missing_imports` | shelling out to converters (unbounded), cloud parsers (content leaves) |
| `ruff` (dev) | format and lint | `black` + `flake8` + `isort` (three tools for one job) |
| `mypy` (dev) | strict types | `pyright` (fine; one checker only) |
| `import-linter` (dev) | layer contracts as configuration | hand-written import tests only |
| `pytest`, `pytest-asyncio`, `pytest-socket`, `pytest-cov` (dev) | the suite, async tests, the socket guard, coverage | `unittest` (no fixtures, no parametrize) |
| `hypothesis` (dev) | property tests for parsers and chunkers | hand-written corpora only |
| `coverage` (dev) | branch coverage and the JSON the floors check reads | — |
| `pip-audit` (dev) | vulnerability audit of the lock | — |
| `testcontainers` (dev) | real PostgreSQL with `pgvector` in storage tests | mocks of the database (banned) |
| `pyyaml`, `types-pyyaml` (dev) | render the contract document as YAML for the backend's tooling; stubs for `mypy --strict`; used only by `tools/` | a committed JSON document (the backend's generator reads YAML), a hand-rolled emitter |

**The first provider's SDK** is a register row added with `ADR-004`'s adapter, adapter-local,
and only if it earns its row over `httpx` against the provider's REST API; the default is
`httpx` because the replay transport then covers it for free.

**Not allowed without a superseding ADR:** any orchestration or "chain" framework, any ORM or
query builder, any DI container, any mocking framework, any assertion DSL, any vector database
client other than PostgreSQL's, any Redis client, a notebook kernel in the runtime image, any
dependency under AGPL or a non-commercial licence, and any package that phones home.

## Invariants

- `INV-021` — every dependency is a register row — `tools/checks/deps`
- `INV-023` — no third-party type crosses the contract or the port — `tools/checks/ports`, `tools/checks/contract`

## Consequences

Provider calls are visible, recordable and budgeted because our code makes them. Some glue is
written by hand — accepted. A model-provider change is an adapter, not a migration of a framework.

## Revisit triggers

- A dependency in the "not allowed" list demonstrates, on this repository's eval sets, a quality
  or cost gain that a hand-written stage cannot match — re-open with the numbers.
- Two adapters duplicate more than the `dupl` threshold of retry, breaker and cost logic that a
  library could own without hiding the call.

## Enforcement

`tools/checks/deps`, `tools/checks/licenses`, `pip-audit`, `tools/checks/ports`, `tools/checks/contract`.
