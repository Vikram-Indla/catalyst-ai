---
id: ARCH-005
title: Providers and the port
status: Locked
version: 1.1.0
owner: AI service lead
created: 2026-09-18
---

# ARCH-005 — Providers and the port

## 1. One port

`src/catalyst_ai/providers/port.py` declares the only way a model is reached:

```
class Provider(Protocol):
    async def generate(self, req: GenerateRequest) -> GenerateResult: ...
    async def stream(self, req: GenerateRequest) -> AsyncIterator[StreamFrame]: ...
    async def embed(self, req: EmbedRequest) -> EmbedResult: ...
    def count_tokens(self, model: ModelAlias, text: str) -> int: ...
```

Request and result types are pydantic models owned by the port: model **alias** (never a concrete
model id), segments (`system`, `developer`, `user[]` with each user segment marked as data),
output schema, temperature, max output tokens, timeout, the tenant's `organization_id` for the
log. A capability calls the port in stage 5 (`ARCH-003 §2`) and nowhere else; a capability
importing an adapter, an SDK, or `httpx` fails `tests/architecture/test_providers_only_via_port`.

## 2. Adapters

`providers/<provider>/adapter.py` implements the port for one provider. The adapter owns, and
the capability never sees:

| Concern | Rule |
| --- | --- |
| Model resolution | alias → concrete model id from the register (`docs/04-ledgers/providers.md`) and configuration; a model id literal outside `providers/<provider>/models.py` and the register fails `tools/checks/models` |
| Timeout | per call, from the capability's budget; never unbounded |
| Retries | idempotent calls only; bounded attempts with exponential backoff and jitter; never on `4xx` except `429` with `Retry-After` |
| Circuit breaker | per provider and model; open on a failure-rate threshold; half-open probes; open ⇒ `ai.provider.unavailable` with `retry_after` immediately, no call |
| Cost accounting | from the provider's usage fields and the register's price row → `cost_micros` in every result |
| Retention | the provider's no-retention/no-training option set on every call; a provider that offers none is refused a register row (`ARCH-002 §4`) |
| Output schema | passed to the provider's structured-output feature where one exists; validated again in stage 6 regardless |
| Errors | mapped to the catalog: `ai.provider.unavailable`, `ai.provider.timeout`, `ai.provider.rejected` (content policy), `ai.provider.quota`; the raw provider message goes to the log under the request id, never to the caller |
| Fault injection | a test-only mode that fails, delays or truncates on demand, for the outage rehearsals runbooks name |

Configuration selects an **alias**, never a model id: `MODEL_TEXT_ALIAS` (and a capability's
own `CAPABILITY_<NAME>_MODEL_ALIAS`) carry one of `text-default`, `text-fast`, `text-long`,
and the register resolves it to the model and its price. An alias outside that vocabulary
fails at settings load rather than at the first call, and no environment can reach a model
the register has not priced (`D-040`). `embed-default` and `grader-default` are not
selectable: changing the first invalidates every stored vector, and the second is the
measuring instrument, not the product (`RULE-008 §3`).

## 3. The recorded transport

Tests never call a provider. `providers/recorded.py` is an `httpx` transport that replays
fixtures from `tests/fixtures/providers/<provider>/<capability>/<case>.json` — request hash,
response body, usage — and fails on a request whose hash has no fixture. `tests/conftest.py`
disables sockets for the whole suite (`pytest-socket`); a test that opens one fails the run.
Re-recording is an explicit `make record CAP=<name> CASE=<case>` with a provider key from the
environment, and the session record states why the provider's behaviour changed (`RULE-004 §4`).

## 4. The first provider, and the next

The first adapter is for the provider the previous system's behaviour was tuned on
(`ADR-004`); its models are the register's first rows. A second provider is a second adapter
behind the same port with its own fixtures, register rows, price rows and retention setting —
and a re-run of every eval set on every capability that switches, with the numbers in the
record. A capability never knows which provider answered; the response's `model` field says.

## 5. Model upgrades

A model change is a configuration change plus an eval run: the alias stays, the concrete id moves
in the register, every eval set that uses the alias runs, the numbers are pasted, and the
decision is a `D-NNN`. A regression is a design error to fix in the prompt or the pipeline —
never a threshold to lower (`RULE-004 §3`).

## 6. Where the provider runs

Every provider call — text, streaming and embeddings — goes to one origin, Vertex AI's regional
endpoint of the configured in-Kingdom location (`PROVIDER_VERTEX_LOCATION`, one of the allowlist in
`config/residency.py`, today `me-central2`; `ADR-008`), under the project the settings
name. A deployed process authenticates as its own workload identity; one module,
`providers/gemini/credentials.py`, obtains the token and forms the header. In staging and
production the settings refuse any other origin, a missing project and a developer's token;
`tools/checks/residency` refuses any other provider host in the source, the tooling and the
operations files (`INV-072`). A register row is **unverified in-region** until the account's
model list shows the region serves the model there; a row that is not served in-region changes
model under §5, never silently.
