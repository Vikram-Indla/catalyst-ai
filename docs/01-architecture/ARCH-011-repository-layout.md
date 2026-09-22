---
id: ARCH-011
title: Repository layout
status: Locked
version: 1.0.1
owner: AI service lead
created: 2026-09-18
---

# ARCH-011 — Repository layout

Every kind of file has exactly one home. A file in the wrong place fails `tools/checks/structure`.
A package is one responsibility and splits when its files stop sharing one — never at a number;
packages over ten files are reported as a smell, not failed.

```
catalyst-ai/
├── src/catalyst_ai/
│   ├── app.py                    the composition root: settings, middleware, routers, lifespan
│   ├── cli.py                    `catalyst-ai` entry point: serve · worker · migrate · check · record
│   ├── contract/                 request, response and error models; a leaf (imports nothing internal)
│   │   ├── common.py  errors.py  jobs.py  <capability>.py
│   ├── config/                   the one Settings object and its validation; the only reader of os.environ
│   ├── platform/                 the shared kernel — one package per capability, no product noun
│   │   ├── errors/  logging/  observability/  budgets/  cache/  tenancy/  safety/  storage/  clock/  ids/  jobs/
│   ├── providers/
│   │   ├── port.py               the Provider protocol and its request/result models
│   │   ├── recorded.py           the replay transport for tests
│   │   └── <provider>/           adapter.py  models.py  errors.py  pricing.py
│   ├── retrieval/                corpora.py  chunking.py  embeddings.py  search.py  parsers/
│   └── capabilities/<name>/      descriptor.py  pipeline.py  schema.py  prompt_vN.md  postprocess.py  routes.py
├── api/openapi.yaml              rendered from the models by `make api`; committed; drift fails CI
├── evals/<name>/                 set.jsonl  graders.py  thresholds.yaml  README.md
├── db/migrations/                forward-only SQL, one per change, timestamped
├── ops/                          alerts.yaml (the rules over the ops port's metrics) · dashboards/*.json
├── tests/
│   ├── unit/                     mirrors src/catalyst_ai/ — one test module per logic module
│   ├── architecture/             the fitness tests (ARCH-012 §4)
│   ├── contract/                 every operation called through the app with recorded fixtures; schema asserted
│   ├── fixtures/                 recorded provider responses, sample documents, golden files
│   └── conftest.py               socket disabled; settings for tests; the recorded transport
├── tools/
│   ├── checks/                   one module per gate (RULE-006); gate.py runs them; gitinfo.py reads git; selftest/ with plants/<check>/
│   ├── rules.py                  the rule vocabulary as data: banned stems, content keys, code roots, floors, layers
│   ├── api.py  install.py  ci_steps.py   render the document · fetch pinned binaries · print the workflow steps for make ci
├── docs/                         00-START-HERE · 01-architecture · 02-rules · 03-adr · 04-ledgers · 05-threat-models · 06-runbooks · 07-GLOSSARY
├── brain/                        01-STATUS · 02-DECISIONS · 03-FINDINGS · 04-OPEN-QUESTIONS · sessions/
├── .githooks/                    pre-commit (fast gate) · commit-msg (conventional) · pre-push (full gate + make ci)
├── .github/workflows/ci.yml      checkout · setup · make tools · make hooks · make verify — nothing else
├── Makefile  pyproject.toml  uv.lock  ruff.toml  mypy.ini  pytest.ini  .coveragerc  .importlinter
├── Dockerfile  docker-compose.yml  .env.example  .tool-versions
└── ENGINEERING.md  README.md
```

## 1. Tool configuration lives in its own files

`pyproject.toml` holds metadata and dependencies only; `ruff.toml`, `mypy.ini`, `pytest.ini`,
`.coveragerc` and `.importlinter` hold their tools' configuration. The Docker dependency layer
copies `pyproject.toml` and `uv.lock` alone, so a lint or coverage edit never invalidates the
resolved environment. Reused from a sibling service where the cost of the alternative was
measured in minutes per build; kept here for the same reason.

## 2. Placement questions, first yes wins

1. Is it wiring (settings load, middleware order, router mount, CLI)? → `app.py` or `cli.py`.
2. Does the backend see it (a request, a response, an error code)? → `contract/`.
3. Does it read the environment? → `config/` — and nowhere else.
4. Does it call a model? → `providers/<provider>/` behind `port.py`.
5. Does it embed, chunk, parse or search? → `retrieval/`.
6. Does exactly one capability use it? → `capabilities/<name>/`.
7. Do two capabilities use it, and it is infrastructure (errors, cache, budgets, safety, ids)? → `platform/<name>/`.
8. Do two capabilities use it, and it is a product noun? → stop; a `Q-NNN` — the service holds no product concept.
9. Is it a check? → `tools/checks/<name>.py` with a plant under `tools/checks/selftest/plants/<name>/`.
10. Is it a prompt? → `capabilities/<name>/prompt_vN.md`; never a string in code.
11. Is it an eval case or grader? → `evals/<name>/`.
12. Is it a recorded provider response, a document sample or a golden file? → `tests/fixtures/`.

## 3. Banned names

Filename stems and package names `service`, `manager`, `helper`, `helpers`, `util`, `utils`,
`common`, `base`, `misc`, `shared`, `data`, `index`, `core`, `lib`, `types`, `models` (outside
`providers/<provider>/models.py`), `v2`, `new`, `final`, `temp`, `tmp`, `stuff` fail
`tools/checks/naming`. The list lives once, in `tools/rules.py`.
