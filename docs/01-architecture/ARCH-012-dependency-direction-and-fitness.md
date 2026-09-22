---
id: ARCH-012
title: Dependency direction and architecture fitness
status: Locked
version: 1.0.1
owner: AI service lead
created: 2026-09-18
---

# ARCH-012 — Dependency direction and architecture fitness

Python has no compiler to refuse an import; the graph is kept legal by `import-linter`
contracts and by fitness tests that run first in `make test`. This page declares the only
directions that exist.

## 1. Layers, one direction

```
routes (capabilities/*/routes.py) ─▶ capabilities/<name> ─▶ platform · retrieval · providers.port
                                                              │
providers/<provider> ─▶ providers.port · platform             ▼
retrieval ─▶ platform · providers.port                     contract  (a leaf)
config ─▶ (nothing internal)
app.py, cli.py ─▶ everything (the composition roots)
```

| From | May import | May never import |
| --- | --- | --- |
| `contract` | stdlib, pydantic | anything internal |
| `config` | stdlib, pydantic-settings, `contract` | anything else |
| `platform/<x>` | stdlib, `contract`, `config`, `providers/port` (the seam type, itself a leaf), other `platform/<y>` (acyclic) | `capabilities`, `providers/<provider>`, `retrieval` |
| `providers/port` | stdlib, pydantic, `contract` | adapters, `capabilities` |
| `providers/<provider>` | `providers/port`, `platform`, `config`, the provider SDK or `httpx` | `capabilities`, `retrieval`, another adapter |
| `retrieval` | `platform`, `providers/port`, `config`, `contract` | `capabilities`, `providers/<provider>` |
| `capabilities/<name>` | `contract`, `platform`, `retrieval`, `providers/port`, `config` | another capability, `providers/<provider>`, an SDK, `httpx`, `os.environ` |
| `app`, `cli` | everything | — |

The law, verbatim:

> A capability may depend on the platform, on retrieval and on the provider port. A capability
> never depends on another capability, on a provider adapter, or on the network. The reverse
> dependency — anything below depending on a capability — is forbidden.

## 2. Contracts in `.importlinter`

`layers` (routes → capabilities → platform/retrieval/port → contract), `independence` (every
`capabilities/<name>` package independent of every other), `forbidden` (capabilities →
adapters, SDKs, `httpx`, `os`; `contract` → anything internal; `platform` → capabilities). A
contract naming a package that does not exist is an error, so the layer packages exist from the
scaffold.

## 3. Interfaces only at substitution boundaries

A `Protocol` exists where a real substitution does: the `Provider` port (adapters and the
recorded transport), `Storage` and `JobStore` (PostgreSQL and the in-memory test double),
`Clock`, `Cache`.
A protocol with one implementation that is not in the seams list fails
`tools/checks/interfaces`.

## 4. Fitness tests

`tests/architecture/` runs first in `make test`; a red test is reported as
`ARCHITECTURE VIOLATION: <invariant>` and names the file. Changing one is a Level-3 decision.

```
test_no_product_schema_import               test_no_product_database_config
test_service_never_calls_backend            test_every_request_field_is_classified
test_no_restricted_field_in_contract        test_every_tenant_table_has_rls
test_every_storage_query_is_tenant_scoped   test_capabilities_are_independent
test_providers_only_via_port                test_contract_is_a_leaf
test_platform_holds_no_product_noun         test_config_is_the_only_environment_reader
test_every_capability_has_descriptor        test_every_capability_has_eval_set
test_every_capability_declares_budget       test_every_capability_has_kill_switch
test_every_operation_lists_error_codes      test_every_error_code_is_catalogued
test_no_model_id_outside_register           test_no_prompt_string_in_code
test_every_prompt_file_has_header           test_pipeline_stages_in_order
test_no_interface_without_substitution      test_no_banned_names
```

## 5. What the ledgers print

`make ledgers` writes the capabilities, errors, config, providers and eval-sets ledgers from the
descriptors, the catalog, the settings object and the register, and reports fan-in and fan-out
per platform package. A platform package that gains a product noun is a finding.
