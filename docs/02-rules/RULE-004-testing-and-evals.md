---
id: RULE-004
title: Testing and evaluation
status: Binding
version: 1.0.0
owner: AI service lead
created: 2026-09-18
---

# RULE-004 — Testing and evaluation

Tests are the executable form of the rules; evals are the executable form of "good enough".
Both ship in the same change as the behaviour and both run on every change.

## §1 Floors

| Layer (package kind) | Floor | Why this number |
| --- | --- | --- |
| `platform/safety`, `platform/tenancy`, `platform/budgets`, `platform/cache` keys, `config/`, and every function an invariant names | **100%** | a branch here is a security, tenancy or cost boundary; an untested branch is a hole |
| `capabilities/*/pipeline.py`, `schema.py`, `postprocess.py`, `retrieval/` (pure parts), `contract/` | **95%+** | deterministic logic; every branch is cheap to test and a real defect if missed |
| `platform/*` (the rest), `providers/port.py` | **90%+** | orchestration; branches are error paths, each reachable |
| `providers/<provider>/`, `platform/storage/`, `retrieval/parsers/`, `routes.py` | **80%+** | covered mostly by contract tests and recorded fixtures; the remainder is defensive plumbing |
| Overall | **90%+** | the whole-repository floor |
| `app.py`, `cli.py`, `tools/`, `tests/`, `evals/graders` | excluded | wiring and the gate itself; the ignore list is reviewed |

`tools/checks/coverage` classifies each module by path and applies the floor; the
classification and the ignore list change only through a `D-NNN`. Reused from the sibling's
per-layer idea; tightened from its 60% global backstop to a 90% floor and from "not yet built"
to a check that exists from the scaffold.

## §2 The pyramid

| Layer | Where | Runs against | What it proves |
| --- | --- | --- | --- |
| Architecture | `tests/architecture/` | the import graph, the tree, the descriptors, the register | every invariant in `ARCH-012 §4`; first in `make test` |
| Unit | `tests/unit/` mirroring `src/` | pure code; the port replaced by the recorded transport or a hand-written double | every stage, every branch, every error; table-driven with `pytest.mark.parametrize` and named ids |
| Property | `tests/unit/**/test_*_property.py` | pure code with `hypothesis` | every parser, chunker, delimiter and encoder round-trips or rejects |
| Contract | `tests/contract/` | the FastAPI app in-process with recorded fixtures and the in-memory storage double | every operation: happy path, each listed error code, tenant scoping, schema validity of the response, the stream's terminal frame |
| Safety | `tests/unit/platform/safety/` and each capability's `test_injection.py` | pure code and recorded fixtures | injection cases in, leakage cases out, `RESTRICTED` refused |
| Budget | `tests/unit/capabilities/<name>/test_budget.py` | the eval run's measurements | p95 latency and p95 cost under the descriptor |
| Storage | `tests/storage/` | real PostgreSQL with `pgvector` (testcontainers) | every query, RLS, tenant scoping, migrations, the retention job |
| Eval | `evals/` via `make evals` | recorded fixtures | every grader above its floor (`ARCH-007`) |

Doubles exist only for the port, storage, the clock and the cache, and are hand-written; no
mocking framework, no `MagicMock` in `src/`-facing tests (`tools/checks/tests`).

## §3 What every capability must have

- A contract test per operation named `test_<operation>_<scenario>`, covering the happy path,
  every listed error code, a request from a second organisation not seeing the first's cache or
  index, and the kill switch.
- Injection cases: at least one instruction embedded in each user-supplied field.
- Leakage cases: a completion carrying a foreign identifier, a secret pattern, an unrequested URL.
- A degradation test: the provider down, the provider timing out, the provider returning
  schema-invalid text twice.
- A budget test and an eval set with a non-empty `injection` tag (`ARCH-009 §2`).
- For a streaming operation: a test that a mid-stream failure ends in an `error` frame.
- For a job operation: idempotency by request hash, expiry, and a second organisation unable to read the job.

## §4 No network, ever

`tests/conftest.py` disables sockets for the suite (`pytest-socket`, `--disable-socket
--allow-hosts=` empty; the storage tests allow only the container's host). A provider call in a
test goes through `providers/recorded.py`; a request without a fixture fails with the hash the
recording needs. Re-recording (`make record`) is a human action with a key from the environment
and a sentence in the session record naming the provider behaviour that changed. Re-recording to
hide a regression is the one thing this repository calls dishonest.

## §5 Shape

- Named cases; the id states the behaviour (`"rejects a title that asks the model to ignore its instructions"`).
- Assertions with `assert` and pydantic equality; no assertion DSL.
- Golden files in `tests/fixtures/golden/`, updated with `--update-golden`, reviewed as diffs.
- A test never sleeps; it advances the injected clock.
- A bug fix begins with the regression test that fails on `main`; a quality regression begins
  with the eval case that fails on `main`.

## §6 The eval gate

`make evals` runs every set, writes `eval_runs`, and fails below any floor or over any budget
(`ARCH-007 §3`). A change to a prompt, a pipeline, a grader, a chunking parameter, a model alias
or a threshold pastes the before-and-after numbers into the session record. A grader believed
wrong is an `F-NNN` with the evidence; the gate stays red until the grader is fixed by its own
ticket — never by lowering the floor.
