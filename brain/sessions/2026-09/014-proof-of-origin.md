# 014 — proof of origin: only the backend can make this service work

**Date:** 2026-09-24 · **Ticket:** AI-015 · **Capability or package:** platform/auth (rewritten), platform/observability (security events), platform/storage (the nonce table), the contract's authentication · **Author:** a contributor

## Read
`ARCH-009` (the token was one string, same for every request and every organisation, compared
in constant time and otherwise unbounded), `ARCH-004 §1` (the `Bearer` row), `ADR-002`,
`ADR-007` (the job model: defined, never built — `catalyst-ai worker` prints that the table does
not exist; every capability is `sync` or `stream`; `reembed` and `retention` are operator
commands, not queued rows), `platform/auth/middleware.py` (a `BaseHTTPMiddleware` over the
bearer), `platform/ids`, the storage port and both adapters, the settings, the way every contract
test presented the bearer (a header on the client), the reviewer's pipeline notes (the same
"trust nothing on PATH" instinct applied to trusting a row), the backend's `ARCH-007 §1, §3`
(deny by default; every token stored hashed; nothing signed outbound today — the signing half is
new there too).

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-015
Capability or package: platform/auth — envelope, keys, verifier, middleware (pure ASGI), jobs; platform/observability/security;
                 platform/storage — remember_nonce on the port, both adapters, the auth_nonces migration; config — auth_public_keys,
                 the two tolerances; contract — auth.origin.invalid, auth.origin.unverifiable, the CatalystEnvelope scheme;
                 tools/checks/origin; tools/origin (the signer for tests and tooling)
Inputs:          the Authorization header (a signed envelope), the request body bytes (hashed), the route (its capability)
Tenant boundary: strengthened — the envelope's org must equal the body's organization_id, before any route
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged (fourteen sets; the eval kit signs like the backend)
Budget:          unchanged
Failure mode:    a request without the backend's signature served → refused before any route, one code, no detail, logged with the reason;
                 a job row trusted for being in the table → verified again before it runs, quarantined otherwise (born verified)
Cache:           unchanged
Safety:          the service holds no signing key and no shared secret; a leak on this side forges nothing (tools/checks/origin)
Contract:        CHANGE, breaking on the only caller by D-035: the bearer is removed, not kept; two codes added, one removed; three variables
Invariants:      INV-052, INV-053, INV-054 (new)
Blast radius:    SYSTEM — the authentication of every operation, one migration, one dependency, the settings
Decision level:  3
ADR:             none new; ADR-003 §3 gains the cryptography row; ARCH-004 1.1.0, ARCH-009 1.1.0, RULE-003 1.0.1 (the code family's name)
```

## Changed
- `platform/auth/envelope.py` — the wire form: `Catalyst-Envelope <claims>.<signature>`; claims a bounded JSON object (`iss`, `aud`, `org`, `cap`, `sub`, `iat`, `exp`, `jti`, `kid`, `bh`, `job_exp?`); `decode` verifies nothing and names why a header is not an envelope (`Malformed`, eleven reasons, for the log)
- `platform/auth/keys.py` — the registry of public keys by `kid` (one or two, parsed by the settings); the only `cryptography` import in the tree; `verify` answers for the named key only
- `platform/auth/verifier.py` — signature, issuer, audience, `exp - iat ≤ AUTH_MAX_TTL_SECONDS`, the window with `AUTH_CLOCK_SKEW_SECONDS`, the body hash, the organisation, the capability, then the nonce once through the storage port; a storage outage is `unverifiable` (fail closed)
- `platform/auth/middleware.py` — pure ASGI (the body is read once, hashed, verified, replayed to the app); the capability of the route through FastAPI's included-router wrappers (F-027); a refusal is `401 auth.origin.invalid` with one fixed message, or `503 auth.origin.unverifiable` with `Retry-After`; an unknown path is refused like anything else; `/healthz` and `/readyz` exempt; the verified envelope on `request.state` for audit
- `platform/auth/jobs.py` — `StoredProof`, `verify_stored`, `JobState` (with `quarantined`), `Quarantine` (`no_job_window`, `job_expired`): the worker's gate, built before the table (D-036)
- `platform/observability/security.py` — `security_event` (ids and the reason, never a claim's text) and `SecurityCounters` held by the app for the metrics endpoint to read
- storage: `remember_nonce` on the port; the memory adapter; PostgreSQL through `nonce_forget` + `nonce_remember` in one transaction, no tenant; migration `20260924100000_auth_nonces.sql` (platform state, no policy, grants to both roles)
- settings: `service_tokens` removed; `auth_public_keys` (required, parsed and bounded), `auth_clock_skew_seconds` (0..60, 5), `auth_max_ttl_seconds` (1..300, 60); `catalyst-ai check` loads the registry and refuses to start without a key
- contract: `AUTH_ORIGIN_INVALID` (401) and `AUTH_ORIGIN_UNVERIFIABLE` (503) replace `AUTH_INVALID`; the document declares `CatalystEnvelope` (http, scheme `Catalyst-Envelope`) globally and `security: []` on the health routes; `make api` regenerated it
- `tools/checks/origin` (+ plant): no signing primitive, no key generation, no `cryptography` outside the registry, no bearer or service token word anywhere in `src/`; red on its plant, 47/47
- `tools/origin.py` — the backend's half for tests and tooling: a signer over a fixed public seed (never a secret), `SigningAuth` for httpx (signs the exact bytes, the body's tenant, the route's capability, against the app's clock), `unsigned` for the tests of the door; the eval kit and the renderer configure the matching public key
- tests: `tests/contract/test_origin.py` (served; organisation mismatch refused without detail and logged with it; replay; expired, unknown key, edited payload; the old bearer and a missing header; the outage as 503), `tests/unit/platform/auth/test_{envelope,keys,verifier,jobs,middleware}.py` (every reason, skew, swap, forgery under a known id, rotation, the attacker's rows quarantined, the job window), `tests/unit/platform/observability/test_security.py`, the nonce test in `tests/storage`; every contract test signs through the client (twelve `_client` helpers, the shared fixture); the probes in `test_platform` became signed POSTs with a tenant
- docs: `ARCH-004 §1` (1.1.0), `ARCH-009 §1` and `§5` (1.1.0), `ARCH-001`, `ARCH-002`, `ADR-002` wording, `ADR-003 §3` (the register row), `RULE-003` (the code family's name, 1.0.1), the config, errors and invariants ledgers, the changelog entry with the "backend must" lines, `THREAT-001-platform.md` (twelve threats; the file the index had promised since the scaffold), `docs/06-runbooks/{key-rotation,quarantine}.md`, `.env.example`
- `pyproject.toml`, `uv.lock` — `cryptography==50.0.0` (with `cffi`, `pycparser`; the first pin, 46.0.5, was refused by `pip-audit` with six advisories — the audited version is the one that stays)

## Verify
```
$ make verify
GATE GREEN (45 checks) · oasdiff: no breaking change against main · 761 passed in 181 s · coverage 99 % (floor 90; the auth package at its 100 % floor) · storage green · fourteen sets EVALS GREEN · pip-audit: no known vulnerabilities · selftest: 47/47 checks red on their plant
VERIFY GREEN
```
```
$ make ci
GATE GREEN (45 checks) · oasdiff: no breaking change against main · 761 passed · coverage 99 % · EVALS GREEN · No known vulnerabilities found · selftest: 47/47 checks red on their plant
VERIFY GREEN
stamp: tree 7185e5519d27 in python:3.12.14-slim at 2026-09-22T08:44:59+00:00 -- green
(this block was written after the stamp; the push's own run re-proves the tree)
```
The attacker-path tests, by name: `test_the_attackers_rows_are_quarantined` (seven rows: no envelope, a made-up one, an envelope copied onto another organisation's row, onto another capability's, a payload edited after the API stored it, an unknown key, a wrong issuer), `test_a_forged_signature_under_a_known_key_id_is_quarantined`, `test_a_job_needs_its_own_window_and_stops_when_it_closes`, `test_organisation_mismatch_is_refused_without_detail_and_logged_with_it`, `test_a_replayed_envelope_is_refused_the_second_time`, `test_expired_unknown_key_and_edited_payload_are_refused`, `test_the_old_bearer_and_a_missing_header_are_refused_alike`, `test_rotation_two_keys_verify_and_a_retired_one_refuses`, `test_a_replay_store_outage_is_a_retryable_refusal_not_a_verdict`; `tools/checks/origin` red on its plant (4). `grep -rn "service_token\|SERVICE_TOKEN\|Bearer " src` → nothing.

## Decisions and questions
- D-035 (the envelope, the bearer removed, unknown paths refused alike, `cryptography` for the verify call), D-036 (jobs born verified).
- F-026: the ticket assumed a job table and a worker; neither exists. The request half is complete; the job half is the verified shape the table is born to (`verify_stored`, `quarantined`, the two columns), and the "real worker loop" acceptance line is not provable until a card builds `ADR-007`'s table — Q-017.
- F-027: FastAPI 0.141 wraps included routers; the capability lookup walks into them.
- The first `make verify` was red at `oasdiff`: 382 errors, every one the error-code enum gaining a value — the catalog had been rendered as a closed `enum`, so every new code was a breaking change on paper. The document now declares it `x-extensible-enum` (the renderer's last step, after the envelope's schemas are merged); `oasdiff breaking` against `main` reports nothing. The removal of `auth.token.invalid` stands under D-035.
- Not done, stated plainly: alert rules as code — the ticket defers their format to the operational-readiness ticket (AI-014), which defines it; this record leaves the two counters (`origin_refused{reason}`, `job_quarantined{reason}`) and the two runbooks for that ticket to wire into alerts. mTLS is a deployment decision and stays out, as the ticket says.

## Commit
1. Files: `src/**`, `tools/**`, `tests/**`, `db/migrations/20260924100000_auth_nonces.sql`, `docs/**`, `brain/**`, `pyproject.toml`, `uv.lock`, `.env.example`
   Proposed: `feat(auth): a signed envelope per request, the bearer gone, jobs born verified`
2. Files: `api/openapi.yaml`
   Proposed: `gen: the contract document declares the proof of origin`
Green light: given

## Next
The backend's signing half (its own change against the changelog entry); the job table's card (Q-017); AI-014, which wires the counters into alerts.
