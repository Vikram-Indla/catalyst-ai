---
id: ADR-005
title: Evaluation before prompts — versioned sets with thresholds as floors, run on every change against recorded fixtures
status: Accepted
date: 2026-09-18
deciders: AI service lead
supersedes: —
superseded_by: —
level: 3
---

# ADR-005 — Evaluation

## Context

The previous system shipped ~30 assisted functions with no eval set; quality was an impression
in a demo and a complaint in production, and a prompt that worked on the tenth document failed
on the eleventh with nobody able to say when it started. A model provider changing a model's
behaviour is indistinguishable from a regression in our prompt unless a fixed set measures both.
The only honest measure of an assisted feature is an evaluation set run on every change, with
the number in the record.

## Options considered

1. **Golden outputs with exact match** — deterministic and brittle; a synonym is a failure; the
   set rots with the first model change.
2. **Human review before release** — honest and unrepeatable; a regression in a corner case is
   found by a customer.
3. **Model-graded everything** — cheap to write, expensive to trust; the grader drifts with the
   model it grades.
4. **Versioned sets of properties with deterministic graders first, model-graded rubrics only
   where nothing deterministic exists, thresholds as floors, run against recorded fixtures in
   the gate, live runs as a human action** — this decision.

## Decision

Every capability has `evals/<name>/` — cases, graders, thresholds, a README with the set's
version and provenance — built **before** its prompt from the behaviour the product wants.
Graders score properties (schema validity, length, language, identifier preservation, no new
facts, groundedness by provenance, forbidden content) deterministically; a model-graded rubric
is allowed only where no deterministic grader measures the property, with its prompt versioned
and its human agreement recorded. Thresholds are floors: the gate (`make evals`) fails below
any of them or over the budget; a floor is raised when earned and lowered only by a `D-NNN`
with the reason in the governing ADR. The gate runs against recorded fixtures, so it is
deterministic and free; `make evals-live` re-records after a model change as a human action.
Every session that touches a prompt, a pipeline, a grader, a chunking parameter or a model alias
pastes the scores and the p95s before and after. Retrieval has its own sets (recall@k).
Regressions from production become anonymised, approved cases the same week.

## Invariants

- `INV-011` — every capability has an eval set with thresholds and a non-empty `injection` tag — `tools/checks/capabilities`, `tools/checks/evals`
- `INV-017` — a threshold is never lowered without a `D-NNN` — `tools/checks/evals`
- `INV-018` — every prompt file carries its header naming the set and the score it was measured on — `tools/checks/prompts`
- `INV-019` — the eval gate runs against recorded fixtures only — `pytest-socket`, `tools/checks/network`

## Consequences

The first cost of a capability is its set, which is the point. Cases are synthetic or
lead-approved — never tenant data — so the set can live in the repository. A regression is a
red gate, not a customer. A grader found wrong is a finding, never a lowered floor.

## Revisit triggers

- A capability whose property cannot be graded deterministically or by a rubric with recorded
  human agreement above 0.8 — its acceptance line must change, or it does not ship.
- Recorded-fixture evals pass while live spot checks fail twice in a month — the recording
  cadence is re-opened.

## Enforcement

`make evals`, `tools/checks/evals`, `tools/checks/budgets`, `tools/checks/prompts`,
`tools/checks/capabilities`.
