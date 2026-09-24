---
id: ADR-008
title: Tenant text is processed in the Kingdom only — the provider is Vertex AI's regional endpoint for a configured in-Kingdom location, reached as the workload's own identity
status: Accepted
date: 2026-09-24
deciders: AI service lead, the lead
supersedes: ADR-004 (the provider's endpoint and credential only; the port, the aliases and the adapter's duties stand)
superseded_by: —
level: 3
---

# ADR-008 — The provider in the region

## Context

Every capability sends tenant text classed `CONFIDENTIAL` to a model: stories, threads, documents,
and, for retrieval, every chunk that is embedded. The lead decided that this text is processed
inside the Kingdom and nowhere else. The first adapter (`ADR-004`) called the provider's
Developer API (`generativelanguage.googleapis.com`) with an API key. That API offers no regional
processing: whatever region the service runs in, the text would be processed wherever the
provider chooses. The same models are served by the provider's Vertex AI platform, whose
**regional** endpoints process a request in the region they name; its global and multi-region
endpoints do not promise that. `me-central2` (Dammam) is the region in the Kingdom.

A deployed process on the provider's platform can be issued short-lived access tokens for the
service account it runs as, by the metadata server beside it, so no long-lived secret needs to
exist. The account that reaches `me-central2` is billed through the regional reseller, and that
account does not exist yet: which models the region serves in-region, rather than routing them
elsewhere, cannot be read until it does.

## Options considered

1. **Keep the Developer API** — no work; tenant text leaves the Kingdom. Refused by the lead.
2. **Vertex AI's global or multi-region endpoint** — the same models, the same adapter; the
   request may be processed in any region. Does not meet the requirement.
3. **Vertex AI's regional endpoint in `me-central2`, as the workload's identity** — this decision.
4. **A model hosted in the region by the service itself** — no provider in the path; a GPU
   estate, a new eval baseline, and none of the measured prompts carry over. Out of proportion
   until option 3 is shown not to serve a model a capability needs.

## Decision

The region is configuration: `PROVIDER_VERTEX_LOCATION` chooses it, and the rule is the allowlist of
in-Kingdom locations in `config/residency.py` (today one entry, `me-central2`), refused outside it
in every environment. The provider's origin is built from the location
(`https://{location}-aiplatform.googleapis.com`), and every call — text, streaming and embeddings —
goes to `/v1/projects/{project}/locations/{location}/publishers/google/models/{id}:{method}`. A
second in-Kingdom region is one allowlist line plus configuration, never a code change. Text uses
`generateContent` and `streamGenerateContent`, embeddings `predict` (one instance per text with
its task type, 768 dimensions, priced by the tokens the provider counts). In staging and
production the settings refuse a missing location, any origin but the location's own, a missing
project, and a developer's token, so the process does not start. A deployed process
authenticates as its own workload identity: `providers/gemini/credentials.py` asks the metadata
server for a token, caches it until a minute
before it expires, and forms the `Authorization` header, the only module that does. The service
account holds the platform's user role on its own project only. In development a developer may
set their own short-lived token (`PROVIDER_ACCESS_TOKEN`) from their own login, and `make record`
reads one the same way (`RECORD_PROVIDER_TOKEN`); no key exists anywhere, and none is committed.
Every register row is marked **unverified in-region** until the account's model list shows the
region serves it there.

## Invariants

- `INV-072` — tenant text is sent only to the regional endpoint of an in-Kingdom location: a location outside the allowlist is refused everywhere; outside development the settings refuse a missing location, any other origin, a missing project and a developer's token; and no provider host but an allowed location's endpoint is named in the source, the tooling or the operations files — `tools/checks/residency` (red on its plant), the settings' residency tests, the adapter's regional-endpoint test
- `INV-053` — unchanged in substance: the service holds no secret shared with the backend; the provider's token is the workload's, formed in one module — `tools/checks/origin`

## Consequences

The adapter, the settings, the recorder and every fixture moved to the regional shape; every eval
set re-ran on authored fixtures with the same numbers. Nothing in the service can reach a model
until the account exists, and then only through its workload identity. The egress rule for the
service narrows to the regional host and the telemetry collector. The price rows are the
provider's published list prices, re-read for the regional platform with the model list.

What must now be done, when the account exists: read the model list for `me-central2`; a row the
region serves in-region loses its mark; a row it does not serve in-region changes model, and every
capability on it re-runs its eval before the change is proposed — a model decision for the lead
with the numbers, never a silent swap. Until then no live recording is made.

## Revisit triggers

- The account's model list shows the region does not serve, in-region, a model an eval floor was
  measured on, and no served model meets that floor — option 4 is re-opened.
- The provider changes what a regional endpoint promises about where a request is processed.
- The lead's residency requirement changes.

## Enforcement

`tools/checks/residency` (row in `RULE-006`), `tools/checks/origin` (the one module that forms the
provider's header), the settings' residency tests, the credentials and embedding tests, the
adapter's regional-endpoint test, the register test that keeps every row unverified in-region.
