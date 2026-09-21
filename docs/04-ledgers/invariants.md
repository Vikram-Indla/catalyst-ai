# Invariants registry

The machine vocabulary of the architecture. Every ADR, impact matrix, finding and pull request
names the invariants it touches by ID instead of describing them; every row names the check that
keeps it true. `tools/checks/invariants` fails CI when a row's enforcement names a test or check
that does not exist, and when a test in `tests/architecture/` is not claimed by a row.

Written by hand; rows are added with the ADR or rule that introduces them and never renumbered.
Criticality: **Critical** = a breach is a security, tenancy or data-integrity incident;
**High** = architectural drift that compounds; **Medium** = cost or quality.

| ID | Invariant | Owner | Enforcement | Criticality | Source |
| --- | --- | --- | --- | --- | --- |
| INV-001 | Every tenant table carries `organization_id NOT NULL`, indexed | platform/storage | `tools/checks/tenancy`, `tools/checks/migrations` | Critical | ADR-002, ADR-006 |
| INV-002 | Every query on a tenant table is scoped by `organization_id` | platform/storage | `tools/checks/tenancy`, `test_every_storage_query_is_tenant_scoped` | Critical | ADR-002 |
| INV-003 | Every tenant table has RLS enabled with the `app.org_id` policy | platform/storage | `test_every_tenant_table_has_rls` | Critical | ADR-006 |
| INV-004 | The application database role cannot bypass RLS | platform/storage | the storage suite's raw-connection case (`SET ROLE catalyst_ai_app`, no `WHERE`: only the set organisation's rows; a write for another organisation refused); `FORCE ROW LEVEL SECURITY` on every tenant table | Critical | ADR-006 |
| INV-005 | No module imports a product schema or configures the product database | boundary | `test_no_product_schema_import`, `test_no_product_database_config` | Critical | ADR-002 |
| INV-006 | The service never calls the backend — no URL, no credential, no callback | boundary | `test_service_never_calls_backend` | Critical | ADR-002, ADR-007 |
| INV-007 | Every request field declares a data class | contract | `tools/checks/classification`, `test_every_request_field_is_classified` | Critical | ARCH-002 §3 |
| INV-008 | No `RESTRICTED` field exists in the contract; values matching secret or personal patterns are refused at the door | contract, platform/safety | `tools/checks/classification`, `test_no_restricted_field_in_contract`, safety tests | Critical | ARCH-002 §3 |
| INV-009 | A cache entry, a job and an index row are scoped by organisation; identical inputs in two organisations produce two rows | platform/cache, retrieval | `tools/checks/tenancy`, contract tests | Critical | ARCH-008 §3, ARCH-006 §3 |
| INV-010 | No tenant input trains or fine-tunes anything; every provider call sets no-retention | providers | register rows, `catalyst-ai check` | Critical | ARCH-002 §4 |
| INV-011 | Every capability has an eval set with thresholds and a non-empty `injection` tag | capabilities | `tools/checks/capabilities`, `tools/checks/evals`, `test_every_capability_has_eval_set` | High | ADR-005 |
| INV-012 | A model is reached only through the `Provider` port | providers | `test_providers_only_via_port` | High | ADR-004 |
| INV-013 | No concrete model id appears outside the register and the adapter's `models.py` | providers | `tools/checks/models`, `test_no_model_id_outside_register` | High | ADR-004 |
| INV-014 | Every adapter sets the provider's no-retention option; a provider without one has no register row | providers | register, `catalyst-ai check` | Critical | ADR-004 |
| INV-015 | Every provider call has a deadline, bounded retries and a circuit breaker | providers | `tools/checks/deadlines`, adapter tests | High | ADR-004 |
| INV-016 | Every provider call produces a content-free `provider_calls` row with tokens and cost | providers, platform/observability | `tools/checks/logs`, adapter tests | Critical | ARCH-010 §1 |
| INV-017 | A threshold is never lowered and a budget never widened without a `D-NNN` | evals | `tools/checks/evals`, `tools/checks/budgets` | High | ADR-005, ARCH-008 |
| INV-018 | Every prompt is a versioned file with its header; no prompt string in code; a released prompt is never edited | capabilities | `tools/checks/prompts`, `test_no_prompt_string_in_code`, `test_every_prompt_file_has_header` | High | RULE-008 |
| INV-019 | The eval gate runs against recorded fixtures only | evals | `pytest-socket`, `tools/checks/network` | High | ADR-005 |
| INV-020 | The interpreter version is one value in `.tool-versions`, `pyproject.toml` and the image | build | `catalyst-ai check` | Medium | ADR-001 |
| INV-021 | Every dependency is a register row with a reason | build | `tools/checks/deps`, `tools/checks/licenses` | High | ADR-003 |
| INV-022 | The test suite opens no socket; every provider call in a test replays a fixture | tests | `pytest-socket`, `tools/checks/network` | High | ADR-001, ADR-004 |
| INV-023 | No third-party type crosses the contract or the port; the contract is a leaf | contract, providers | `tools/checks/ports`, `tools/checks/contract`, `test_contract_is_a_leaf` | High | ADR-003 |
| INV-024 | SQL lives only in `platform/storage/queries/`; no `SELECT *` | platform/storage | `tools/checks/sql` | Medium | ADR-006 |
| INV-025 | Every migration is forward-only with a header; every foreign key is indexed | platform/storage | `tools/checks/migrations` | Medium | ADR-006 |
| INV-026 | Every index is rebuildable from what the backend can resend | retrieval | rebuild runbook, retrieval eval | Medium | ADR-006 |
| INV-027 | A synchronous capability's timeout is at most the job line (20 s) | capabilities | `tools/checks/capabilities` | Medium | ADR-007 |
| INV-028 | A job is idempotent by request hash and organisation; a second organisation cannot read it | platform/jobs | job contract tests | Critical | ADR-007 |
| INV-029 | Every job result and cache entry expires; the retention job purges past it | platform/jobs, platform/cache | storage tests | Medium | ADR-007, RULE-009 §4 |
| INV-030 | Capabilities are independent: no capability imports another | capabilities | `import-linter`, `test_capabilities_are_independent` | High | ARCH-012 |
| INV-031 | The pipeline's stages run in order and the port is called only in `call` | capabilities | `tools/checks/pipeline`, `test_pipeline_stages_in_order` | High | ARCH-003 §2 |
| INV-032 | Every capability has a kill switch that returns `ai.capability.disabled` before any call | capabilities, config | `tools/checks/capabilities`, `test_every_capability_has_kill_switch`, contract tests | High | RULE-009 §2 |
| INV-033 | Every route is thin: typed in, typed out, no branch on content | routes | `tools/checks/routes`, `tools/checks/contract` | Medium | RULE-001 §2 |
| INV-034 | Configuration is read only in `config/`; every variable is declared with class and doc | config | `tools/checks/config`, `test_config_is_the_only_environment_reader` | High | RULE-003 §5 |
| INV-035 | The output scanner refuses foreign identifiers, secret patterns and unrequested URLs | platform/safety | safety tests, 100% coverage | Critical | ARCH-009 §3 |
| INV-036 | Per-tenant budgets are enforced in the service before any provider call | platform/budgets | budget tests, contract tests | High | ARCH-008 §2 |
| INV-037 | Every completion is validated against the capability's schema; at most one repair; then `ai.output.invalid` | capabilities | pipeline tests | High | ARCH-003 §2 |
| INV-038 | A stream ends with exactly one terminal frame | contract | contract tests | High | ARCH-004 §4 |
| INV-039 | Every contract change has a changelog entry with the "backend must" line; breaking changes are versioned | contract | `tools/checks/changelog`, `oasdiff` | High | ARCH-004 §6 |
| INV-040 | `make verify` equals CI equals `make ci`; the workflow holds nothing else | build | `tools/checks/ci`, `.githooks/pre-push` | High | RULE-005 §1 |
| INV-041 | The platform holds no product noun; a package that gains one is a finding | platform | `test_platform_holds_no_product_noun` | High | ARCH-011 §2 |
| INV-042 | Every capability package carries a descriptor and declares its budget | capabilities | `tools/checks/capabilities`, `test_every_capability_has_descriptor`, `test_every_capability_declares_budget` | High | ARCH-003 §1 |
| INV-043 | Every operation lists its error codes and every code is catalogued | contract | `tools/checks/errors`, `tools/checks/openapi`, `test_every_operation_lists_error_codes`, `test_every_error_code_is_catalogued` | High | RULE-003 §2 |
| INV-044 | A Protocol exists only at a seam; no banned name exists in the tree | platform | `tools/checks/interfaces`, `tools/checks/naming`, `test_no_interface_without_substitution`, `test_no_banned_names` | Medium | ARCH-012 §3, RULE-001 §4 |
| INV-045 | A proposed workflow scheme leaves the service only after the structural check: one initial in `todo`, a terminal in `done`, every status reachable, endpoints known, guards from the request's vocabulary, a reason on every backward, reject and reopen move | capabilities | `check_scheme` with its unit tests on planted proposals; `structurally_valid` and `every_status_reachable` floors 1.0; contract test on a refused scheme | High | ARCH-002 §2 |
| INV-046 | A digest's counts are the request's, echoed field for field; the service never counts and states no number the data lacks | capabilities | `digest_groups` with its unit test on the count echo; `digest_shape_and_count_echo` and `no_counts_invented` floors 1.0 | High | ARCH-002 §2 |
| INV-047 | An output that becomes a record — a release note, a test case, a post-mortem fact or factor — cites a source id the request carried, or is refused; nothing partial is returned | capabilities | `refuse_untraceable` in `platform/language/records` with its unit test; `no_invented_entries`, `covers_traceable`, `facts_traceable` and `analysis_evidenced` floors 1.0; contract tests on invented entries | High | ARCH-002 §2 |
| INV-048 | A grounded answer leaves the service only when every sentence cites a passage that was retrieved for it from the asked space; otherwise it is refused or `not_found` | capabilities | `check_claims` with its unit tests; `no_uncited_claims` and `citations_resolve` floors 1.0; the contract test on an uncited answer | Critical | ARCH-006 §4 |
| INV-049 | Bytes from a member are parsed only in a child process with a deadline and a ceiling, behind the container, entity, script and size guards; a refusal is a reason class, never a crash and never the bytes | retrieval | `retrieval/runner`, the hostile corpus test, the parser property tests, `documents-ingest` set floor 1.0 | Critical | ARCH-009 §2 |
