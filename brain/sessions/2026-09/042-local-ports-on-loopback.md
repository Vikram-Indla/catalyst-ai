# 042 — The local run: the database on 5434, every port on loopback, no secret in the example

**Date:** 2026-09-24 · **Ticket:** AI-037 · **Capability or package:** `docker-compose.yml`, `.env.example`, tools/checks (`localrun`, the gate's lists, the selftest), `RULE-006` · **Author:** a contributor

The product now runs locally with this service beside the backend: every seeded account shares
one test password, so every port binds loopback, and this database must not take the backend's
5433. The local-up script calls a fixed set of ports and a liveness URL; this change makes the
service answer them, and gives the example file the check the leak scanner cannot be.

## Read
`docker-compose.yml`, `.env.example`, `config/settings.py` (the listen addresses), the health
routes, `tools/checks/gate`, the selftest, `RULE-006`.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-037
Capability:      none — the local run and the gate
Inputs:          unchanged
Tenant boundary: unchanged
Provider/model:  unchanged; with no credentials the capabilities stay off
Prompt version:  unchanged
Eval set:        unchanged
Budget:          unchanged
Failure mode:    none added; a secret value in the example, or a port off loopback or off the agreed
                 set, is refused by the fast gate
Cache:           none
Safety:          nothing published beyond 127.0.0.1; no secret value in the example
Contract:        unchanged
Invariants:      none added (RULE-006's row names the check)
Blast radius:    LOCAL — the compose file, the example, tools/checks
Decision level:  0
ADR:             none
```

## What changed
- **Ports**, all on `127.0.0.1`: the database `5434` (the backend keeps `5433`), the API `8090`, the
  ops ports `9091` (api) and `9092` (worker). Inside the containers the processes listen on every
  interface (`:8090`, `:9091`, set by compose) so the mapping reaches them; nothing is published
  beyond loopback.
- **`.env.example`**, for a process run on the host: the database URL on `127.0.0.1:5434`, and the
  listen addresses `127.0.0.1:8090` / `127.0.0.1:9091`. The development database logins in compose
  and `db/provision/development.sql` are unchanged and development-only, as before.
- **`env_file` stays required — "copy it first".** `cp .env.example .env`, then
  `docker compose up -d`. A missing `.env` stops compose with its name instead of starting the
  service on settings nobody chose; the compose header says so.
- **`tools/checks/localrun`**, in the fast set:
  - it refuses a value in `.env.example` for any secret-shaped key (`*_PASSWORD`, `*_KEY`,
    `*_KEYS`, `*_TOKEN`, `*_SECRET`), commented out or not, except a key named in
    `PUBLIC_BY_DESIGN` with its reason (only `CATALYST_AI_AUTH_PUBLIC_KEYS`, the public
    verification key);
  - it refuses a port `docker-compose.yml` publishes that is not `127.0.0.1`, or not one of the
    four agreed ports.
- `RULE-006` has the row; the selftest plants a password, a commented token and an open port:
  56/56 red.

## Red first
```
main's docker-compose.yml under the new check
  docker-compose.yml@main:19: 5433:5432 is not bound to 127.0.0.1
  docker-compose.yml@main:45: 8090:8090 is not bound to 127.0.0.1
  docker-compose.yml@main:46: 9091:9091 is not bound to 127.0.0.1
  docker-compose.yml@main:59: 9092:9091 is not bound to 127.0.0.1
planted in a copy of the example: DB_PASSWORD=<word>, "# ..._ACCESS_TOKEN=<value>"   -> both refused
after: localrun green on the tree; the tools suite 126 passed; selftest 56/56
```

## The contract, checked (a dry run on the host; Docker is in use by another landing tonight)
```
serve with the example's values, no database running, no provider token:
  GET http://127.0.0.1:9091/healthz -> 200
  GET http://127.0.0.1:9091/readyz  -> {"status":"not_ready","checks":{"settings":true,
                                        "storage":false,"provider_credentials":false,"serving":true}}
  uvicorn listening on http://127.0.0.1:9091 and http://127.0.0.1:8090 (loopback only)
docker compose config -q -> valid; gitleaks on .env.example -> no leaks found
```
The containers themselves start with the next full gate's run of compose, when Docker is free.

## Eval and budget numbers
No capability changed; no eval set moved.

## Verify
Fast checks in the loop: the tools suite, lint, types, the fast gate, the selftest. The full
gate runs before this is pushed; its output is pasted here then.

The full gate on the tree this change is committed from:
```
$ make verify
VERIFY GREEN — GATE GREEN (56 checks) · 1189 passed, coverage 99.41% · EVALS GREEN · selftest 58/58 (on the host, before record 043's make hooks fix)
$ make ci
VERIFY GREEN in catalyst-ai-ci:d06a9811d6b3 — 56 checks · 1189 passed, 99.41% · EVALS GREEN · selftest 58/58 · stamp: tree f777f5806cb3 at 2026-09-25T07:16:19+00:00 -- green
```

## Decisions and questions
- None: the ports are the agreed contract; `env_file` stays required (chosen and stated above).

## Commit
- `build(local): database on 5434, every port on loopback, no secret in the example`
