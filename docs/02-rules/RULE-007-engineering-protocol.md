---
id: RULE-007
title: Engineering protocol — the AI impact matrix, stop conditions, the report
status: Binding
version: 1.0.0
owner: AI service lead
created: 2026-09-18
---

# RULE-007 — Engineering protocol

This service is built by many hands and many tools over many years, around a component that
changes behaviour under them overnight. The principle: **code is disposable; boundaries are
not — and the model is an untrusted input generator.** A contributor may rewrite a stage,
replace a prompt version, refactor inside a capability. It may not casually change what
`RULE-000 §6` lists, and it may not answer a product question in a prompt.

## §0 Reading discipline

Read the minimum relevant context: the pages the ticket names, the files to change, the golden
capability (`improve-story`) where a pattern already exists, and — when the ticket retires a
function of the previous system — that function, for its **behaviour**: inputs, what a good
output looked like, what the user saw. Never its code; the previous functions were prompts glued
to a gateway, and the shape is not worth keeping. If ownership, contract or product intent stays
ambiguous after those reads, stop and ask (`§2`).

## §1 Before writing code — the AI impact matrix

After the reads in `ENGINEERING.md`, and before any edit, the session writes the matrix into its
session record. Empty rows say "none"; a row it cannot fill is a `Q-NNN`, not a guess; an eval
set that does not exist is the first thing the session builds.

```
Ticket:          AI-NNN
Capability:      <name or "none">                       (ARCH-003)
Inputs:          <field · data class> …                 (ARCH-002 §3)
Tenant boundary: <organization_id scope · storage rows touched>
Provider/model:  <provider · model alias from the register> (ARCH-005)
Prompt version:  <prompt_vN or "none">                  (RULE-008)
Eval set:        <evals/<name> vN · thresholds>         (ARCH-007)
Budget:          <p95 latency · p95 cost>               (ARCH-008)
Failure mode:    <error codes · degradation>            (RULE-003 §2)
Cache:           <key · TTL or "none">                  (ARCH-008 §3)
Safety:          <injection · leakage · abuse cases>    (ARCH-009)
Contract:        <operationIds added/changed · breaking?> (ARCH-004)
Invariants:      INV-NNN, …                             (docs/04-ledgers/invariants.md)
Blast radius:    LOCAL / CAPABILITY / CONTRACT / PLATFORM / SYSTEM
Decision level:  0 / 1 / 2 / 3                          (RULE-000 §7)
ADR:             none / ADR-NNN
```

| Radius | Means | Typical change |
| --- | --- | --- |
| `LOCAL` | one module inside a capability, no surface changed | a post-processing fix, a new unit test |
| `CAPABILITY` | one capability, its contract unchanged | a prompt version, a grader, a chunking parameter |
| `CONTRACT` | anything the backend sees | a new field, a new operation, an error code |
| `PLATFORM` | anything under `platform/`, `providers/`, `retrieval/`, `config/` | the cache key, the safety scanner, an adapter |
| `SYSTEM` | anything in `RULE-000 §6` | the boundary, tenancy, retention, a threshold lowered |

## §2 Stop conditions

The session stops and files a `Q-NNN` instead of improvising when the work would need: a second
provider · a new retrieval index or corpus · a contract change the ticket did not name · a new
dependency · a new table · a product decision (tone, language, what to hide, whose name may
appear, what the user sees when the capability is off) · content retention · a threshold lowered
or a budget widened · a new pattern where the golden shape applies · an input the backend cannot
send as classified data · anything the matrix cannot answer. Stopping is the correct outcome.

## §3 Pattern discipline

A contributor may not introduce a new architectural pattern, layer, naming convention, file kind
or package shape when an existing one applies. The reference is the golden capability and the
scaffold from `make new-capability`; a proposed deviation is a `Q-NNN` with the reason the
existing pattern does not fit. Names that were not in the vocabulary yesterday (`service.py`,
`manager.py`, `orchestrator.py`, `chain.py`, `graph.py`, `helpers.py`) are rejected by
`tools/checks/naming`.

## §4 During and after

1. Implement inside the capability or package the ticket names; run its tests and
   `tests/architecture` continuously, `make verify` and `make ci` before claiming done.
2. The report at the end of the session, in the session record, in this order: files changed
   (a plain list) · invariants touched by `INV-` ID · blast radius · contract changed (with the
   changelog entry) · eval score, p95 latency, p95 cost, before and after · budgets · errors and
   degradations · safety cases added · tests added · architectural impact · assumptions made ·
   unresolved questions. No narrative, no praise, no "should work", no "usually".
3. The commit proposal per `RULE-005 §2`.

## §5 What a session never does

Commits without the green light · calls a provider from a test · re-records a fixture to hide a
change · edits a released prompt in place · lowers a threshold or widens a budget · edits an
ADR's decision text · touches `RULE-*` or `ARCH-*` except through a ticket that names them ·
disables a check, widens an allowlist or lowers a floor · adds a `noqa` or `type: ignore` without
an allowlisted reason · logs content · answers a product question in a prompt · fabricates a
value where data is unavailable · writes a comment to explain code it could have made clearer.

## §6 Tool independence

The protocol is the same for every contributor and every tool. `ENGINEERING.md` points here; a
tool-specific file that restates or contradicts this page is a finding.

## §7 The review a contributor runs before "done"

Could this capability leak one organisation's text to another? What happens when the provider
returns garbage that is schema-valid? What does the backend receive when this capability is off?
Which eval case would catch the regression I am most afraid of — and is it in the set?
