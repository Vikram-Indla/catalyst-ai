---
id: RULE-002
title: Python standards — toolchain, types, async, errors, time
status: Binding
version: 1.0.0
owner: AI service lead
created: 2026-09-18
---

# RULE-002 — Python standards

## §1 Toolchain

- **Python 3.12**, pinned in `.tool-versions`, `pyproject.toml` (`requires-python = ">=3.12,<3.13"`)
  and the Docker base image — the three agree or `catalyst-ai check` fails. Tightened from the
  sibling's 3.11 for `typing.override`, the faster interpreter and the type-parameter syntax.
- **`uv`** for environments and locking; `uv.lock` committed; `uv sync --frozen` everywhere
  (hooks, CI, the image). A lockfile change is its own commit (`RULE-005 §2`).
- **`ruff`** for format and lint, configured in `ruff.toml`: `line-length = 100`,
  `quote-style = "double"`, and the select list
  `E W F I N UP B C4 SIM RUF ERA T20 G PTH S PL ANN D ASYNC DTZ LOG PT TRY` with `ANN401`
  selected. Reused from the sibling (its eighteen groups, each justified in the file) and
  extended by `ASYNC` (blocking calls in async code), `DTZ` (naive datetimes), `LOG` (logging
  hygiene), `PT` (pytest style) and `TRY` (exception hygiene). Global ignores: `D203`, `D213`
  (convention pairs) — two, not the sibling's three; `PLR0904` is not ignored because class-heavy
  code is not written here. A new global ignore is a `D-NNN`.
- **`mypy --strict`** in `mypy.ini` with `warn_unreachable`, `warn_unused_ignores`,
  `strict_equality`; `Any` on a boundary signature is refused by `tools/checks/contract`. Escape hatches
  (`ignore_missing_imports`) exist only for SDKs that ship no `py.typed`, only under
  `providers/<provider>` and `retrieval/parsers`, and each is a line in the register with the
  containment reason; `tools/checks/mypy_overrides` fails an override outside those packages.
- **`import-linter`** for the layer contracts (`ARCH-012 §2`).
- **`pytest`** with `pytest-asyncio` (`asyncio_mode = auto`), `pytest-socket` (sockets disabled),
  `hypothesis` for parsers and chunkers, `coverage` with `branch = true`.
- **`pip-audit`** and **`gitleaks`** in `make security`; **`uv`'s** lock verifies hashes.

## §2 Types

Every function is fully annotated (`ANN`); `Any` is a lint error (`ANN401`) unless justified
inline with an allowlisted reason; `cast` is a smell reviewed like `Any`. Pydantic v2 models at
every boundary — request, response, port, job payload, settings — with `extra="forbid"` on
inputs. `TypedDict` is not a boundary type. `Protocol` for seams (`ARCH-012 §3`); `ABC` is not
used. Generic containers are typed to their element (`list[Chunk]`, never `list`).

## §3 Async

The app is `async`; the pipeline is `async`; the port is `async`. Blocking calls (file IO,
CPU-heavy parsing, tokenisers) run in `asyncio.to_thread` or a subprocess — `ASYNC` rules fail a
blocking call in a coroutine. Every awaited IO has a deadline (`asyncio.timeout` or the client's
timeout); an `httpx.AsyncClient` without `timeout=` fails `tools/checks/deadlines`. No
fire-and-forget task: a `create_task` without a holder and a cancellation path fails
`tools/checks/tasks`. Bounded concurrency through `asyncio.Semaphore` with a named constant.

## §4 Errors

Errors are typed: `platform/errors.Error` with a `code` from the catalog, an HTTP status by kind,
`details[]` and a `retry_after`. A capability raises catalog errors; a route never composes one;
the single handler in `app.py` renders the envelope. Provider exceptions are caught in the
adapter and mapped (`ARCH-005 §2`); an SDK exception escaping `providers/<provider>` fails
`tools/checks/errors`. `except Exception` exists only in the adapter's mapping and the
app-level handler (`BLE001` elsewhere). `raise … from err` always (`TRY`).

## §5 Time, ids, randomness

`platform/clock.Clock` is injected; `datetime.now()` in a capability fails `tools/checks/inline`.
Ids are UUID v7 from `platform/ids`; `uuid.uuid4()` inline fails the same check. Randomness
only through an injected `random.Random` seeded in tests; temperature is a descriptor value,
never a literal in a pipeline.

## §6 Tests beside logic

Every logic module under `src/catalyst_ai/` has a test module at the mirrored path under
`tests/unit/`; `tools/checks/tests` fails an orphan. `__init__.py`, `app.py`, `cli.py` and
`descriptor.py` are wiring and exempt by the list in `tools/rules.py`.
