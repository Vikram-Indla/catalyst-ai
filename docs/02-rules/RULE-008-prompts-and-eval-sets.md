---
id: RULE-008
title: Prompts and eval sets — the two versioned artefacts
status: Binding
version: 1.0.0
owner: AI service lead
created: 2026-09-18
---

# RULE-008 — Prompts and eval sets

## §1 A prompt is a versioned file

- `capabilities/<name>/prompt_vN.md`. Never a string in code, never concatenated in code beyond
  filling named placeholders, never edited in place after the capability version that used it
  was released — a change is `prompt_v(N+1).md` and a `capability_version` bump.
  `tools/checks/prompts` fails a string in `capabilities/` that looks like an instruction to a
  model (the heuristics live in `tools/rules.py`) and a released prompt file whose content hash
  differs from the one recorded in the ledger.
- Every prompt file starts with a header:

```
---
capability: improve-story
version: 2
model_alias: text-default
tuned_on: text-default@2026-09
eval_set: improve-story v3
score: 0.84
supersedes: prompt_v1.md
---
```

- Segments are explicit and named: `[system]`, `[developer]`, `[user:<field>]`. Every user
  segment is introduced as data and delimited with the stable marker `platform/safety` owns;
  the prompt tells the model the segment is data and not an instruction.
- A prompt contains no tenant data, no example drawn from tenant data, no person's name.
- Language, tone, formality, what to hide from a user, what to do with a request outside the
  capability's purpose — product decisions. A prompt encodes the decision the lead recorded
  (`D-NNN`); it never makes one. A session that needs one stops (`RULE-007 §2`).

## §2 Assembly

Stage 4 of the pipeline (`ARCH-003 §2`) loads the prompt file by version, fills named
placeholders from the validated request and the retrieved context, and produces the port
request with segments separate. Filling is the only string operation; `f"..."` on a user field
in `capabilities/` fails `tools/checks/prompts`. The output schema is passed to the port; the
model is told the shape and stage 6 validates regardless.

## §3 An eval set is a versioned artefact

- `evals/<name>/` — `set.jsonl`, `graders.py`, `thresholds.yaml`, `README.md` (`ARCH-007 §2`).
  The set has a version in `README.md`; every response carries `eval_set_version`.
- The set is built **before** the prompt: from the behaviour the product wants — the previous
  system's function read for what a good output looked like, the lead's answers to the product
  questions — never from the prompt's own outputs.
- Cases are synthetic or lead-approved; a case carries tags (`happy`, `edge`, `injection`,
  `leakage`, `language:<code>`, `long`, `empty`); the `injection` tag is required non-empty.
- Every prompt change, pipeline change, grader change, model alias change and chunking change
  runs the full set and pastes: score per grader, overall, p95 latency, p95 cost — before and
  after — into the session record.
- Thresholds are floors: raised when a change earns it; lowered only by a `D-NNN` with the reason
  in the governing ADR; `tools/checks/evals` fails a lowered threshold without one.
- A grader believed wrong is an `F-NNN` with the evidence; the gate stays red until the grader's
  own ticket fixes it.
- A regression found in production becomes an eval case the same week, anonymised and approved.

## §4 Model-graded rubrics

Allowed only where nothing deterministic measures the property (fluency, faithfulness beyond
provenance). The grader's prompt is a versioned file under `evals/<name>/grader_prompt_vN.md`
with the same header; its agreement with human labels on a labelled subset is recorded in
`README.md` and re-measured on every grader change; it runs against recorded fixtures like any
call. A model-graded score never stands alone: a deterministic floor sits beside it.

## §5 The two travel together

A change to a prompt is a change to the eval numbers; a change to a grader is a change to what
the prompt is measured against. Neither lands without the other's numbers. The ledger
`docs/04-ledgers/eval-sets.md` records, per capability: set version, prompt version, model
alias, scores, p95s, date, session record.
