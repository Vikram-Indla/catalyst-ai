---
id: ARCH-002
title: The boundary and data classes
status: Locked
version: 1.0.0
owner: AI service lead
created: 2026-09-18
---

# ARCH-002 — The boundary and data classes

The boundary is the product. Everything in this page is an invariant with a fitness test
(`ARCH-012 §4`); changing any of it is a Level-3 decision (`RULE-000 §6`).

## 1. One caller, one contract

- The backend is the only caller. Every request carries the service token; there is no user
  session, no cookie, no per-user credential. The backend has already authenticated the user,
  checked the permission, and decided that this capability may run on this input.
- The contract is `api/openapi.yaml`, generated from the pydantic models in `contract/` and
  committed; the backend generates its client from it. Nothing reaches the service that is not
  in the document (`ARCH-004`).
- The service never calls the backend, never holds a backend URL or credential, never subscribes
  to a backend event. Dependency direction is one way (`ADR-007`, `INV-006`).

## 2. No product table, no product fact

- The service has no connection string to the product database, no generated client for it, no
  copy of its schema. `tests/architecture/test_boundary.py` fails on any import, module or
  configuration variable that names a product table or the product database.
- The service's own database (`ARCH-006`) holds only what the service produces: embeddings, cache
  rows, eval runs, job rows, the content-free provider log. Every tenant-owned row carries
  `organization_id NOT NULL` with row-level security; a query without it fails `tools/checks/tenancy`.
- What a capability needs, the backend sends in the request, classified (§3). A capability that
  needs a *rule* — which transitions are legal, which item types exist — receives the rule as data
  (`type_list`, `allowed_transitions`) and validates against it; it never decides the rule.
- The result is a proposal: `improved_text`, `proposed_children`, `summary`, `matches` with
  scores and provenance, `confidence`. The backend stores it, shows it, or discards it. The
  service never writes a work item, sends a notification or makes a product decision.

## 3. Data classes at the door

The backend's classification applies to every field of every request, declared in the contract:

| Class | Examples | May enter the service | May reach a provider | May be stored here | May appear in logs |
| --- | --- | --- | --- | --- | --- |
| `PUBLIC` | type names, workflow state names, language codes | yes | yes | yes | yes |
| `INTERNAL` | item keys, project keys, status names, sprint names | yes | yes | yes (per tenant) | IDs only |
| `CONFIDENTIAL` | item titles and descriptions, comments, page text, document text, chat messages | yes | yes, under the retention rule (§4) | as embeddings and cache values, per tenant, with TTL | never the value |
| `RESTRICTED` | names, emails, IPs, credentials, tokens, secrets, anything the backend marks personal | **no** — `ai.input.rejected` | never | never | never |

- Every request model declares each field's class in its schema metadata
  (`Field(json_schema_extra={"data_class": "CONFIDENTIAL"})`); `tools/checks/classification`
  fails a field without one and a `RESTRICTED` field anywhere in a request model.
- The door rejects `RESTRICTED` structurally: the contract has no field that carries it, and the
  input scanner (`platform/safety`) refuses values that match secret and credential patterns
  with `ai.input.rejected` and a reason class — the backend fixes the caller; the service never
  "cleans" the input.
- People are `RESTRICTED`. A capability that needs to refer to a person (a digest, a standup
  summary) receives an opaque label the backend chose (`participant_1`, a handle the product
  deems `INTERNAL`); the service never receives a name or an email (`Q-001`).

## 4. Retention and training

- No tenant input is used to train, fine-tune, or evaluate a model beyond the request that
  carries it; eval sets are synthetic or lead-approved (`RULE-008 §3`).
- Provider settings that permit the provider to retain or train on inputs are refused in
  configuration: the adapter sets the no-retention option the provider offers, and
  `catalyst-ai check` fails when the register row for a model lacks a documented retention
  setting (`docs/04-ledgers/providers.md`).
- Content is never logged (`ARCH-010`). Sampling content for quality review exists only as a
  per-organisation opt-in in configuration, off by default, with a retention limit (`Q-002`).

## 5. Fitness tests that keep the boundary

`test_no_product_schema_import`, `test_no_product_database_config`, `test_every_request_field_is_classified`,
`test_no_restricted_field_in_contract`, `test_service_never_calls_backend`, `test_every_tenant_table_has_rls`,
`test_every_storage_query_is_tenant_scoped` — `ARCH-012 §4`.
