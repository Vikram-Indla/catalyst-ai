---
id: RULE-009
title: Lifecycle — capability versions, kill switches, deprecation, retention
status: Binding
version: 1.0.0
owner: AI service lead
created: 2026-09-18
---

# RULE-009 — Lifecycle

## §1 Capability versions

`capability_version` is semantic: a patch is a post-processing or bug fix with no eval delta
beyond noise; a minor is a prompt version, a grader, a chunking change, an additive field; a major
is a breaking contract change, which is a new path version (`ARCH-004 §6`). The descriptor
carries the version; the ledger and every response carry it; `tools/checks/capabilities` fails
a prompt version bump without a capability version bump.

## §2 The kill switch

Every capability has `CATALYST_AI_CAPABILITY_<NAME>_ENABLED` in the settings tree, default
`true`; `false` makes stage 2 return `ai.capability.disabled` before any provider call, cache
read or index query. The runbook line says what the backend shows. A capability without the
setting fails `tools/checks/capabilities`; the contract test asserts the switch.

## §3 Deprecation

A retiring operation or field carries `Deprecation` and `Sunset` headers or schema
`deprecated: true`, a replacement named in the changelog, and a sunset date at least one minor
release away. `tools/checks/deprecations` fails an operation past its sunset and a deprecation
without a replacement.

## §4 Retention

| Row family | Retention | Purged by |
| --- | --- | --- |
| `cache_entries` | the capability's TTL | the retention job |
| `jobs` and results | `job_result_ttl` (default 24 h) | the retention job |
| `provider_calls` | `provider_log_retention_days` (default 90) | the retention job |
| `embeddings_*` | until the backend's forget call or organisation deletion | `knowledge.forget`, `organizations.delete` |
| `eval_runs` | kept (synthetic data) | — |
| quality samples (`ARCH-010 §4`) | the opt-in's limit | the retention job |

Organisation deletion is one operation the backend calls (`POST /v1/organizations/{id}:delete`)
that removes every tenant row across every family and writes one content-free audit row; the
contract test proves zero rows remain.

## §5 Flags

Behaviour flags beyond the kill switch are temporary, carry a removal ticket in the settings
docstring, and never live in a pipeline (a pipeline branches on data, not on flags);
`tools/checks/flags` fails an expired flag.
