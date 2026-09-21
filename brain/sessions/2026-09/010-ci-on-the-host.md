# 010 — the workflow's first run on the host: git before checkout, a named database

**Date:** 2026-09-22 · **Ticket:** AI-009 (follow-up) · **Capability or package:** the workflow, tests/storage · **Author:** a contributor

## Read
The first hosted run of `ci` on `main` (`e9d0921`): failed in 21 s at `make hooks` with `fatal: not
a git repository`. `RULE-005 §1`, `RULE-006 §2`, `tools/checks/ci`, the `make ci` target, the
hosted runner's container-job behaviour: `actions/checkout@v4` downloads a tarball through the
API when no `git` is on the PATH at checkout time, so the tree has no `.git`; a container job has
no Docker of its own, so the storage tests and the retrieval eval could not start their
throwaway pgvector container even once the checkout was a repository.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-009 (follow-up)
Capability or package: .github/workflows/ci.yml · tests/storage/conftest.py · the config ledger
Inputs:          none (no request surface)
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged — the sets run as before; the search set reads the named database when one is given
Budget:          unchanged
Failure mode:    the workflow: a red run where the gate is green locally; fixed by ordering, not by a new step
Cache:           unchanged
Safety:          the same steps in the same image (RULE-005 §1); the service container holds throwaway dev credentials only
Contract:        unchanged
Invariants:      INV-002 (CI equals the gate: the steps are the allowed four, reordered; `tools/checks/ci` green)
Blast radius:    LOCAL — the workflow file, one fixture, one ledger paragraph
Decision level:  1
ADR:             none
```

## Changed
- `.github/workflows/ci.yml` — the setup line (`apt-get … git … pip install uv`) runs **before** `actions/checkout@v4`, so the checkout is a real clone with `.git` (the hosted checkout falls back to a tarball when `git` is absent); a `services.postgres` container (`pgvector/pgvector:pg17`, throwaway credentials, a health check) and `CATALYST_AI_EVAL_DATABASE_URL` pointing at it — the same four run steps, the same image, nothing added that the gate does not run
- `tests/storage/conftest.py` — `database_url` yields `CATALYST_AI_EVAL_DATABASE_URL` when it is set, as `tools/evalkit` already did, else the container as before
- `docs/04-ledgers/config.md` — the tooling variable named

## Verify
```
$ make verify
ruff / mypy / lint-imports                                   All checks passed! · Success · Contracts: 5 kept, 0 broken.
tools.checks.gate --skip coverage,budgets                     GATE GREEN (43 checks) (ci: the four steps, reordered)
tools.api · oasdiff                                           matches the app · no breaking change against main
pytest tests/architecture · pytest --cov                      24 passed · 633 passed in 127.18s · Total coverage: 99.45% · GATE GREEN (1 checks)
pytest tests/storage · make evals · budgets                   4 passed · EVALS GREEN (twelve sets unchanged) · GATE GREEN (1 checks)
pip-audit / gitleaks / licences · selftest                    No known vulnerabilities found · no leaks found · GATE GREEN · 45/45 red on their plant
VERIFY GREEN
```
```
$ make ci
$ make ci     (python:3.12.14-slim, the workflow's steps verbatim)
All checks passed! · Success · Contracts: 5 kept, 0 broken. · GATE GREEN (43 checks) · oasdiff: no breaking change against main
24 passed · 633 passed in 219.56s · Total coverage: 99.45% · GATE GREEN (1 checks) · pytest tests/storage: 4 passed
EVALS GREEN · GATE GREEN (1 checks) · No known vulnerabilities found · no leaks found · GATE GREEN (1 checks)
selftest: 45/45 checks red on their plant
VERIFY GREEN
```
The named-database path, proven on the host with a service-shaped container (`docker run pgvector/pgvector:pg17`, the variable set): `pytest tests/storage` 4 passed · `tools.evals --set search` overall 0.950, EVALS GREEN.

## Decisions and questions
- none new; the workflow keeps `RULE-005 §1` to the letter (`tools/checks/ci` green with the reordered steps)

## Commit
1. Files: `.github/workflows/ci.yml`, `tests/storage/conftest.py`, `docs/04-ledgers/config.md`, `brain/sessions/2026-09/010-ci-on-the-host.md`
   Proposed: `ci: git before checkout, a named pgvector service for the hosted run`
Green light: given by the lead on 2026-09-22 (the failed hosted run)

## Next
Watch `ci #2` on `main`; the assistant card.
