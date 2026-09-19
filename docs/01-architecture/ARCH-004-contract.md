---
id: ARCH-004
title: The contract
status: Locked
version: 1.0.0
owner: AI service lead
created: 2026-09-18
---

# ARCH-004 — The contract

## 1. Contract first, models as the source

The pydantic models in `src/catalyst_ai/contract/` **are** the contract. `make api` renders them
through the FastAPI app into `api/openapi.yaml` (OpenAPI 3.1), which is committed; CI fails on
drift between the rendered document and the committed one (`tools/checks/openapi`). The backend
generates its client from the committed file, so the models are written before the pipeline,
reviewed as the design, and never changed without a changelog entry (`RULE-003 §1`).

The direction is models → document (the reverse of the backend's spec → code) because Python's
runtime validation *is* the pydantic model; a hand-edited YAML would be a second source. The
committed document is still the artefact the caller consumes, and the drift check is what makes
the two one.

## 2. Shape

| Aspect | Rule |
| --- | --- |
| Base path | `/v1/` — additive changes only; a breaking change is `/v2/` for the affected operation, the old one carrying `Deprecation` and `Sunset` headers for at least one minor release |
| Operation | `POST /v1/<capability>` for synchronous capabilities; `POST /v1/<capability>:jobs` + `GET /v1/jobs/{id}` for long ones; `POST /v1/<capability>:stream` for streaming (`ADR-007`) |
| `operationId` | `<capability>.<verb>` (`improve_story.run`, `knowledge_ingest.submit`, `jobs.get`) |
| Authentication | `Authorization: Bearer <service token>` on every operation; `401` with `auth.token.invalid` otherwise |
| Tenant | `organization_id` (UUID) is a required field of every request body and a required query parameter of every `GET`; never inferred |
| Idempotency | `Idempotency-Key` header honoured on every `POST`; the same key and organisation returns the cached result for the cache TTL (`ARCH-008 §3`) |
| Casing | JSON `snake_case` (the models' own field names; no alias layer to drift) |
| Time | RFC 3339 UTC strings; durations as integer milliseconds with `_ms` in the name |
| Money | cost as integer micro-dollars (`cost_micros`) — never floats |
| Versions | every response carries `capability_version`, `prompt_version`, `model`, `eval_set_version` (`ARCH-003 §3`) |
| Usage | every response carries `usage: { input_tokens, output_tokens, cost_micros, latency_ms, cache_hit }` |
| Confidence | every generated result carries `confidence` in `[0, 1]` from a deterministic grader where one exists; `null` where none does, never a guess |
| Provenance | every retrieved or grounded result carries `provenance[]` — the chunk, item key or page each claim rests on |
| Errors | one envelope: `{ error: { code, message, details: [{ field, code, message }] }, request_id }` (`RULE-003 §2`) |
| Long operations | `202` + `Location: /v1/jobs/{id}`; `jobs.get` returns `{ status, result?, error?, expires_at }` |
| Rate limits | per organisation and per capability; `429` with `Retry-After` and `ai.budget.exceeded` |
| Deprecation | `Deprecation` and `Sunset` headers; one minor release notice minimum |

## 3. The boundary is typed

A route function takes one request model and returns one response model. `dict[str, Any]`,
`Any`, a bare `dict` or a raw JSON body in a route signature, a pipeline surface or a port
method fails `tools/checks/contract`. Response models are the allowlist: unknown fields never
leak, and `model_config = ConfigDict(extra="forbid")` is required on every request model so a
caller that sends a field the service does not know is told so.

## 4. Streaming

`POST /v1/<capability>:stream` returns `text/event-stream`. Frames are typed:
`delta` (`{ text }`), `citation` (`{ provenance }`), `usage` (once), and exactly one terminal
frame — `done` (`{ result }`, the validated response model) or `error` (the envelope). A stream
that closes without a terminal frame is a defect the contract test catches; the backend treats
it as `ai.provider.unavailable`.

## 5. Errors

Error codes are constants in `contract/errors.py`, `ai.<family>.<condition>`, each with an HTTP
status and a documented degradation (`RULE-003 §2`, `docs/04-ledgers/errors.md`). A route may
return only the codes its operation lists (`x-error-codes` in the rendered document, taken from
the descriptor); `tools/checks/errors` fails an orphan in either direction.

## 6. Compatibility

Expand/contract only: a new field is optional first; a field is removed one version after the
changelog entry with the "backend must" line; a type change is a new field. `oasdiff breaking`
against `main` fails CI without a version bump. Every change to the document adds an entry to
`docs/04-ledgers/contracts-changelog.md`: date, ticket, operations, kind, what the backend must
do now.
