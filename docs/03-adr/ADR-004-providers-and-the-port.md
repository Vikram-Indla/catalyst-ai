---
id: ADR-004
title: One Provider port; the first adapter is the provider the previous system was tuned on; aliases, not model ids
status: Accepted
date: 2026-09-18
deciders: AI service lead
supersedes: —
superseded_by: —
level: 3
---

# ADR-004 — Providers and the port

## Context

The previous system reached four providers through two gateways (`_shared/llm.ts`,
`lovable-ai.ts`), named concrete models inside functions (`gemini-2.5-flash`,
`gemini-2.5-flash-lite`, two Anthropic models, one OpenAI model, an OpenAI embedding model),
retried inconsistently, counted cost nowhere, and cached in a table that ignored tenancy. Most
of its behaviour — and every eval case this repository will start from — was tuned on Google's
Gemini 2.5 Flash family. Providers change models under callers overnight; a capability that
names a model is a capability that breaks silently.

## Options considered

1. **A provider SDK called from each capability** — quickest; untestable without the network;
   a second provider means editing every capability.
2. **A gateway service between this service and the providers** — one more process, a
   second contract, and the same port needed on this side anyway.
3. **One port in this service, one adapter per provider, aliases resolved by the register** —
   this decision.

## Decision

`providers/port.py` declares `Provider` (`generate`, `stream`, `embed`, `count_tokens`) with
pydantic request and result models; a capability calls the port and nothing else. Capabilities
name a **model alias** (`text-default`, `text-fast`, `text-long`, `embed-default`,
`grader-default`); the register (`docs/04-ledgers/providers.md`) and configuration resolve
each alias to one provider and one concrete model id, with its price row, its context limit and
its retention setting. The first adapter is for **Google Gemini**, over `httpx` against the REST
API unless the SDK earns a register row, with the `text-default` alias resolving to the model
the previous system was tuned on; every eval set is measured on it first. A second provider is
a second adapter behind the same port, its own fixtures and register rows, and a full eval
re-run on every capability that switches. Adapters own timeouts, bounded retries with jitter,
a per-provider circuit breaker, cost accounting from usage fields, error mapping to the catalog,
the no-retention setting, and fault injection for rehearsals. Tests replay recorded fixtures
through the `httpx` transport seam; nothing in the suite touches a provider.

## Invariants

- `INV-012` — a model is reached only through the port — `test_providers_only_via_port`
- `INV-013` — no concrete model id appears outside the register and the adapter's `models.py` — `tools/checks/models`
- `INV-014` — every adapter sets the provider's no-retention option; a provider without one has no row — register, `catalyst-ai check`
- `INV-015` — every provider call has a deadline, bounded retries and a breaker — `tools/checks/deadlines`, adapter tests
- `INV-016` — every provider call produces a content-free `provider_calls` row with cost — `tools/checks/logs`, adapter tests
- `INV-022` — the suite opens no socket; every call replays a fixture — `pytest-socket`, `tools/checks/network`

## Consequences

A model upgrade is a register edit plus an eval run plus a `D-NNN`. A capability never knows
which provider answered; the response's `model` field does. Adding a provider costs an adapter,
fixtures and an eval re-run — the right price. The provider's structured-output feature is
used where present and never trusted alone (`ARCH-003 §2` stage 6).

## Revisit triggers

- An alias's eval score on the first provider falls below a capability's floor after a provider
  model change, and no prompt or pipeline fix recovers it — a second adapter earns its row.
- Cost per call on `text-default` exceeds the family budget on two consecutive eval runs.
- The provider removes its no-retention option — the adapter is disabled by the kill switch on
  every alias it serves until a replacement is measured.

## Enforcement

`tools/checks/models`, `tools/checks/network`, `tools/checks/deadlines`, `tools/checks/logs`,
`test_providers_only_via_port`, the adapter's fault-injection tests.
