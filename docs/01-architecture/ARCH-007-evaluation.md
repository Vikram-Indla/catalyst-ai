---
id: ARCH-007
title: Evaluation
status: Locked
version: 1.0.0
owner: AI service lead
created: 2026-09-18
---

# ARCH-007 — Evaluation

## 1. Evaluation is the regression suite

A test proves the code does what it says; an eval measures whether the output is good enough
against a named set. Both run on every change; only the eval has thresholds. No capability
exists without an eval set (`INV-011`); the set is built before the prompt (`RULE-008 §3`).

## 2. Shape of a set

```
evals/<capability>/
  set.jsonl          one case per line: id, input (a request model), expected properties, tags
  graders.py         deterministic graders first; model-graded only where nothing deterministic exists
  thresholds.yaml    per grader: the floor; overall: the floor; p95_latency_ms; p95_cost_micros
  README.md          set version, provenance of the cases (synthetic / lead-approved), what a "good" output is
```

- Cases are synthetic or lead-approved. Raw tenant data never enters a set; a case derived from
  a production failure is anonymised and approved before it lands (`ARCH-002 §4`).
- A grader is a function of `(case, response) -> Score` in `[0, 1]`. Deterministic graders —
  schema validity, length bounds, language, forbidden content, required fields, identifier
  preservation, no new facts — come first. A model-graded rubric is allowed only where nothing
  deterministic measures the property; its prompt is versioned like any prompt, and its
  agreement with human labels on a labelled subset is recorded in `README.md`.
- Thresholds are floors. Raised when a change earns it; lowered only by a `D-NNN` with the
  reason in the ADR that governs the capability. `tools/checks/evals` fails a lowered threshold
  without a `D-NNN` reference in the same change.

## 3. The gate

`make evals` runs every set against the recorded fixtures (`ARCH-005 §3`) and writes
`eval_runs`; the gate fails when any grader falls below its floor, when the overall score does,
or when p95 latency or p95 cost crosses the budget (`ARCH-008 §1`). Recorded fixtures make the
gate deterministic and free; a *live* run (`make evals-live CAP=<name>`) is a human-triggered
action with a provider key, used to re-record after a model change, and its numbers go in the
session record.

## 4. Retrieval evals

Retrieval has its own set: labelled queries with relevant chunk ids; graders are recall@k,
precision@k and MRR; thresholds sit in `evals/<corpus>-retrieval/thresholds.yaml`. Generation
over retrieved context is graded separately for groundedness (every claim has a provenance
entry that supports it).

## 5. Where the numbers go

Every session that touches a prompt, a pipeline, a model alias, a chunking parameter or a grader
pastes the full set's scores, the p95 latency and the p95 cost into the session record beside
the previous run. A change that improves the score and doubles the cost is a decision, not a
win; the record says which.
