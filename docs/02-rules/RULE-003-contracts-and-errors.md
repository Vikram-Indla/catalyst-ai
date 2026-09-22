---
id: RULE-003
title: Contracts, errors, the port and configuration
status: Binding
version: 1.0.1
owner: AI service lead
created: 2026-09-18
---

# RULE-003 — Contracts, errors, the port and configuration

A contract is anything the backend relies on: an operation, a request or response shape, an
error code, a header, a stream frame, a job status, a configuration variable, a port method.
Elaborates `ARCH-004`.

## §1 The contract

- The request and response models are written in `contract/<capability>.py` **before** the
  pipeline; the route is thin (`RULE-001 §2`). The rendered document (`make api`) is committed
  as `api/openapi.yaml`; `tools/checks/openapi` fails on drift, on an operation without
  `x-capability`, `x-capability-version`, `x-error-codes` and an example, and on a request
  field without `data_class`.
- Every response model extends `contract/envelopes.ResponseEnvelope`: `capability_version`,
  `prompt_version`, `model`, `eval_set_version`, `usage`, `request_id`; generated results add
  `confidence` and `provenance[]` where the family requires (`ARCH-004 §2`).
- Every request model extends `contract/envelopes.RequestEnvelope`: `organization_id`,
  `capability_version` (the version the caller was built against; a mismatch is
  `ai.contract.version_mismatch`), and `extra="forbid"`.
- No free-form objects. `dict[str, Any]` in a contract model fails `tools/checks/contract`; a
  structured field is a nested model.
- `oasdiff breaking` against `main` fails CI; a breaking change is a new path version with the old
  one carrying `Deprecation` and `Sunset` for at least one minor release.
- Every change to the document adds an entry to `docs/04-ledgers/contracts-changelog.md`: date,
  ticket, operations, kind (`ADD` / `CHANGE` / `DEPRECATE` / `REMOVE` / `FIX`), and **what the
  backend must do now**. `tools/checks/changelog` fails a document diff without a changelog diff.

## §2 Errors

- Codes are constants in `contract/errors.py`: `ai.<family>.<condition>`, with an HTTP status
  and a documented degradation. The families: `ai.input` (`rejected`, `too_large`,
  `unsupported`), `ai.provider` (`unavailable`, `timeout`, `rejected`, `quota`), `ai.output`
  (`invalid`, `unsafe`), `ai.budget` (`exceeded`), `ai.capability` (`disabled`, `unknown`),
  `ai.contract` (`version_mismatch`), `ai.index` (`unavailable`, `rebuilding`), `ai.job`
  (`not_found`, `expired`, `failed`), `auth.origin` (`invalid`, `unverifiable`),
  `validation.invalid_input`, `internal.error`. `docs/04-ledgers/errors.md` is generated from
  the module.
- The envelope is `{ error: { code, message, details[] }, request_id }` everywhere including
  `401`, `404`, `429` and `500`. `500` carries `internal.error` and nothing else — the detail is
  in the log under the request id. A provider's raw message never reaches the caller.
- A route may return only the codes its descriptor lists; `tools/checks/errors` fails a raise
  of an unlisted code and a listed code nothing raises.
- Messages are developer-facing English, stable, and free of interpolated input.

## §3 The port

`providers/port.py` exports the `Provider` protocol and its models, made only of pydantic
models, builtins, `datetime`, `UUID` and the port's own enums. No SDK type, no `httpx` type
crosses the port in either direction (`tools/checks/ports`). A port method is one call; an
adapter never calls back into a capability.

## §4 Jobs

Job payloads are versioned pydantic models (`kind = "knowledge_ingest.v1"`) carrying
`organization_id`, the request hash and the request model; the worker is idempotent by request
hash; a status is one of `queued`, `running`, `succeeded`, `failed`, `expired` (`ADR-007`).

## §5 Configuration

Every environment variable is declared in `config/settings.py` with its type, whether it is
required, its validation, its data class and its documentation string; `docs/04-ledgers/config.md`
is generated from the class. Reading `os.environ` anywhere else fails `tools/checks/config`.
The prefix is `CATALYST_AI_`. Secrets are `SecretStr` and never rendered. Per-capability settings
(`model alias`, `enabled`, `cache_ttl_seconds`, budgets) are a nested model keyed by capability
name; `catalyst-ai check` fails on a capability in the tree without its settings row and on a
settings row without its capability.
