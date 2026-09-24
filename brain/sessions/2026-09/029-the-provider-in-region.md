# 029 — the provider in the region

**Date:** 2026-09-24 · **Ticket:** AI-024 · **Capability or package:** providers/gemini (adapter, credentials, embedding, models), config (settings, residency), tools (checks/residency, checks/origin, record, evalkit, authored), every provider fixture, `ADR-008` · **Author:** a contributor

The lead decided that tenant text is processed inside the Kingdom and nowhere else. The adapter
called the provider's Developer API with a key, which processes wherever the provider chooses.
This moves text, streaming and embeddings to Vertex AI's regional endpoint in `me-central2`,
reached as the workload's own identity, before any live credential exists.

## Read
`ADR-004`, `ARCH-002 §4`, `ARCH-005`, `ARCH-009 §5`, `RULE-006`; the adapter, the settings, the
origin check, the recorder, the stand-in; the providers and config ledgers; the platform's
published regional-endpoint and embedding request shapes.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-024
Capability:      every capability (the provider under them); no capability code changes
Inputs:          unchanged
Tenant boundary: tenant text now processed in me-central2 only
Provider/model:  same models, regional platform; every row unverified in-region
Prompt version:  unchanged
Eval set:        unchanged; every set re-run on re-authored fixtures
Budget:          unchanged (same list prices, re-read with the model list)
Failure mode:    a wrong origin in a deployed process -> it refuses to start; a token the metadata
                 server will not issue -> every call fails as the provider's rejection, no text sent
Cache:           the workload token cached until a minute before expiry; response caches unchanged
Safety:          no long-lived credential anywhere; the developer token refused outside development
Contract:        no operation changes; settings change (changelog entry)
Invariants:      INV-072 (new); INV-053 unchanged in substance
Blast radius:    PLATFORM — every provider call
Decision level:  3
ADR:             ADR-008 (supersedes ADR-004's endpoint and credential only)
```

## What moved
- **The origin.** `config/residency.py` names the region and its endpoint. Every call goes to
  `/v1/projects/{project}/locations/me-central2/publishers/google/models/{id}:{method}`. The
  settings validator refuses, in staging and production, any other origin, a missing
  `PROVIDER_VERTEX_PROJECT`, and a developer's token.
- **The credential.** `providers/gemini/credentials.py` is the one module that forms the provider's
  header. A deployed process asks the metadata server for its service account's token and caches it
  until a minute before expiry. There is no key: `PROVIDER_GEMINI_API_KEY` is gone. The service
  account needs the platform's user role on its own project only; that grant is the deployment's,
  not this repository's.
- **The local answer.** A developer who wants a live local run sets `PROVIDER_ACCESS_TOKEN` to their
  own short-lived token from their own login. `make record LIVE=1` reads `RECORD_PROVIDER_TOKEN` and
  `PROVIDER_VERTEX_PROJECT` the same way. Both are refused outside development, expire with the
  login, and are never written to a file the repository tracks. Authored inputs only, until the lead
  allows otherwise.
- **Embeddings.** `providers/gemini/embedding.py`: `predict`, one instance per text with its task
  type, 768 dimensions, vectors normalised, the call priced by the tokens the provider counts per
  vector, with the character estimate when it reports none.
- **The register.** Same rows, and every row carries `residency = "unverified in-region"`. A test
  keeps them all so until the model list is read. The retention sentence now names the project's
  data terms, to be verified with the account.
- **The checks.** `tools/checks/residency` (new, in the gate and the selftest) refuses any provider
  host but the regional one in `src/`, `tools/`, `ops/` and `.env.example`, and refuses settings that
  stop defaulting to or applying the region. `tools/checks/origin` lets the credentials module alone
  name the bearer. It does not count the settings module as a second reader: that module declares
  and validates its secrets, and it tests the developer token's presence without reading it.
- **Fixtures.** Every set's fixtures were re-authored for the regional request shape. The stand-in
  answers `predict` with the platform's response shape.

## Red first
```
test_every_call_goes_to_the_regional_endpoint_with_the_workload_token  red on the old adapter (v1beta, x-goog-api-key)
test_a_deployed_process_sends_tenant_text_only_to_the_region          red before the validator (8 cases: 2 environments x 4)
interfaces: "Protocol TokenSource is not a seam"                      -> a union of the two sources, no Protocol
origin: "config/settings.py reads provider_access_token"              -> the declaring module is not a reader
residency, on the tree: tools/checks/selftest named the Developer API host -> the plant's literal split
selftest: residency red (4 on plant)
```

## Readiness (the delivery review)
`/readyz` gains `provider_credentials`: red until the metadata server has issued the first token,
so a rollout on a node without the workload identity, or with the metadata server blocked, never
takes traffic; red again only once the held token has expired and no refresh succeeded (a failed
refresh inside the token's life stays ready). `/healthz` stays process-only. The probe is carried
by the runtime (`RuntimeContext.credentials_ready`, set by the composition root from the adapter),
not by the Provider port: a first version added `ready()` to the port, which RULE-005 §6 classes
CRITICAL ("deployed alone"); the end-of-loop gate's class check caught it and it moved. A
developer's token is ready. Red first:
`test_health_ready_stays_red_until_the_provider_credential_is_current` and
`test_ready_waits_for_the_first_token_and_outlives_a_failed_refresh_until_expiry` fail on the
probe without the check. `.env.example` says a developer's token expires within the hour, so a long
`make record` can fail part-way for that reason.

## The region as configuration (the platform answer, after the first build)
The region was a literal in `config/residency.py` and in the check. Now:
- `PROVIDER_VERTEX_LOCATION` chooses it. It is required outside development; development falls back
  to the allowlist's first entry.
- `IN_KINGDOM_LOCATIONS` in `config/residency.py` is the rule and the only place a region is named.
  A location outside it is refused in every environment.
- The endpoint (`https://{location}-aiplatform.googleapis.com`) and the calls' `locations/{location}`
  are built from the setting. `PROVIDER_GEMINI_BASE_URL` became an optional development override.
- `tools/checks/residency` reads the allowlist from the residency module by parsing it, so the check
  names no region. An endpoint of a location not in the allowlist is red, and the same endpoint
  passes once its location is added.
- The settings file reached its 300-line budget, so its cross-field refusals moved to
  `config/deployed.py`, which the origin check treats like the settings module.
- `.env.example` names the location; the config ledger has its row. `ADR-008`, `ARCH-002 §4`,
  `ARCH-005 §6`, `INV-072` and `RULE-006` are reworded; `D-054`.

## Found on the way
The journeys check was red: `interpret_query.run` had no contract test (the unit tests had covered
the route but not the app). `tests/contract/test_interpret_query.py` now covers the checked query,
the refusal outside the grammar, and the switch. It belongs with record 027's proposals.

## The stop line
Which models `me-central2` serves **in-region** (processed there, not routed global) is read from
the model list of the real account. That account is billed through the regional reseller and does
not exist yet. Until it does:
- every register row stays unverified in-region;
- no live call and no live recording is made;
- a row the list does not confirm changes model, and every capability on it re-runs its eval before
  the change is proposed. That is a model decision for the lead, with the numbers.

The service's egress narrows to the regional host and the telemetry collector. That rule lives in
the deployment, and the changelog entry tells the backend's deployment so.

## Verify
Fast checks during the loop: the unit, contract and architecture suites; format, lint, types; the
static gate (green but for the records awaiting the full gate); the eval run on re-authored fixtures
(every set green). The full gate at the end of the loop is pasted in record 027.

## Decisions and questions
- `ADR-008` (Accepted, the lead's decision), `D-050`, `INV-072`; `ARCH-002 §4` and `ARCH-005 §6`.
  ADR-004's `superseded_by` names it for the endpoint and credential only.

## Eval and budget numbers
This change's own numbers are in the record above; the run of every set, with each set's p95
latency and cost against its budget, is in the gate output below.

## The gate at the end of the loop
One full gate proves the whole tree of the loop, every record's change together.
```
$ make verify
(on the workstation, before four records' claims were corrected to CONTRACT — records only)
GATE GREEN (52 checks)
oasdiff: no breaking change against main
TOTAL                                                            7711     27    956     25    99%
1056 passed in 309.82s (0:05:09)
GATE GREEN (1 checks)
EVALS GREEN
GATE GREEN (1 checks)
No known vulnerabilities found
INF no leaks found
GATE GREEN (1 checks)
selftest: 54/54 checks red on their plant
VERIFY GREEN
exit=0 elapsed=628s
```
```
$ make ci
(in catalyst-ai-ci:d06a9811d6b3; the second run — the first was red: 1052 passed, 4 errors in
tests/storage/test_logins.py, SocketConnectBlockedError, fixed as record 031 says)
GATE GREEN (52 checks)
oasdiff: no breaking change against main
TOTAL                                                            7711     27    956     25    99%
1056 passed in 535.13s (0:08:55)
GATE GREEN (1 checks)
EVALS GREEN
GATE GREEN (1 checks)
No known vulnerabilities found
INF no leaks found
GATE GREEN (1 checks)
selftest: 54/54 checks red on their plant
VERIFY GREEN
stamp: tree b51a07c33c09 in catalyst-ai-ci:d06a9811d6b3 at 2026-09-24T12:03:29+00:00 -- green
exit=0 elapsed=1333s
```

## Commit
See the proposal list in record 027.
