---
id: ADR-001
title: Python 3.12 and a boring, typed stack — uv, FastAPI, pydantic v2, ruff, mypy, pytest, hypothesis, httpx, OpenTelemetry
status: Accepted
date: 2026-09-18
deciders: AI service lead
supersedes: —
superseded_by: —
level: 3
---

# ADR-001 — Python and the stack

## Context

The backend is Go, one binary, one contract (`ADR-001` of that repository). The assisted
features it needs — rewriting, structured generation, retrieval, summaries, document
intelligence, an assistant — rest on evaluation harnesses, document parsing (docx, pptx, pdf,
OCR), embeddings and vector search, tokenisers, structured-output validation and batch
experiments, all of which are Python-first by a wide margin. The previous system ran ~30
TypeScript edge functions, each a prompt glued to a gateway, with no eval set, no recorded
tests, no budget and content in logs. A Go proxy would be right for the first week and wrong
after it; a Python service without a hard boundary would become a second backend.

## Options considered

1. **Assisted features inside the Go backend** — one language, one deploy; every eval harness,
   parser and tokeniser rebuilt or wrapped; the team's Python fluency for model work unused.
2. **A Python service with a framework that "orchestrates" models** — fast demos; the provider
   call hidden from the tests, prompts scattered in code, a dependency that changes under us.
3. **A Python service on a boring typed stack behind one contract** — this decision.

## Decision

`catalyst-ai` is Python 3.12, managed by `uv` with a committed lock; `FastAPI` for the contract
surface (it renders the pydantic models into the OpenAPI document the backend consumes);
`pydantic` v2 for every boundary model and the settings object; `ruff` for format and lint;
`mypy --strict`; `pytest` with `hypothesis`, `pytest-asyncio` and `pytest-socket`; `httpx` for
every outbound call with a replay transport in tests; `asyncpg` over PostgreSQL with `pgvector`
in the service's own database; `OpenTelemetry` for traces and metrics; the standard library's
`logging` with one JSON formatter. No orchestration framework, no ORM, no DI container, no
mocking framework, no assertion DSL (`ADR-003`). Python is safe here only because the boundary
(`ADR-002`) keeps it a dependency of the backend and never its peer.

## Invariants

- `INV-020` — the interpreter version is one value in `.tool-versions`, `pyproject.toml` and the image — `catalyst-ai check`
- `INV-021` — every dependency is a register row — `tools/checks/deps`
- `INV-022` — the test suite opens no socket — `pytest-socket`, `tools/checks/network`

## Consequences

Two languages in the product, one contract between them; the backend's generated client is
the only coupling. Glue that a framework would generate is written by hand — accepted, and
partly recovered by pydantic and FastAPI's rendering. Every contributor learns one shape (the
golden capability) and one gate.

## Revisit triggers

- The backend team needs to ship a capability the contract cannot carry without the service
  holding product state — a boundary problem, not a language one; see `ADR-002`.
- A Go ecosystem for evals, parsers and embeddings reaches parity measured on this repository's
  eval sets — re-open with the numbers.

## Enforcement

`tools/checks/deps`, `catalyst-ai check`, `pytest-socket`, `tools/checks/ci`.
