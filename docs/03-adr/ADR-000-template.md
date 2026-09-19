---
id: ADR-000
title: <decision in one line>
status: Proposed | Accepted | Superseded | Deprecated | Rejected
date: YYYY-MM-DD
deciders: AI service lead, <others>
supersedes: —            # ADR-NNN this replaces, if any
superseded_by: —         # filled in when a later ADR replaces this one; never delete an ADR
level: 2 | 3             # RULE-000 §7
---

# ADR-000 — <title>

## Context

What forces are at play: the problem, the constraints, what the previous system did, what is
known and unknown. Facts, with sources. For a capability or model decision: the eval numbers.

## Options considered

1. **Option A** — what it is, what it costs, what it gives.
2. **Option B** — …

## Decision

The choice, in one paragraph, stated so an engineer can act on it without reading the rest.

## Invariants

The statements that are true while this ADR stands, written so a test can assert each one.

- `INV-NNN` — `<invariant>` — kept true by `<test or check>` (new rows are added to `docs/04-ledgers/invariants.md` in the same change)

## Consequences

What becomes easier, what becomes harder, what must now be done (tickets), what this rules out.

## Revisit triggers

The observable conditions under which this decision is re-opened — an eval number, a cost, a
latency, a provider change. An ADR without triggers is a belief, not a decision.

## Enforcement

The rows in `RULE-006` and the tests in `tests/architecture/` that keep the decision true.
