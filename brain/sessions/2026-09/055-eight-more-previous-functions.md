# 055 — Eight more previous functions that called a model, each given a final state

**Date:** 2026-09-25 · **Ticket:** AI-042 (1 of n: the audit) · **Capability or package:** the capabilities ledger (final states, the Retires column), `D-063`, `Q-019`, `Q-020` · **Author:** a contributor

The ledger named forty-one previous functions. A search of the previous system's functions for model
calls found eight more that it never named. Each is read here, with its model, prompt, inputs,
outputs and callers, and given one final state (or deferred until its product area moves). No code changes.

## Read
Each function read in full in the previous system (read-only). Callers found by searching its source
for the function's name.

| Function | Model · prompt | Inputs → outputs | Callers |
| --- | --- | --- | --- |
| `strata-advisory` | Gemini 2.5 Flash, temperature 0.2, JSON · "advisory variance briefing … use ONLY the facts" | a period's KPI achievements, scorecard scores, benefits, value at risk, open exceptions → `{narrative ≤ 180 words, confidence}`, stored as a draft for review | the strategy module's domain layer |
| `report-insights` | Gemini 2.5 Flash, 0.2 · summary, ≤ 4 highlights, ≤ 3 risks, ≤ 2 actions, "never invent numbers" | a test report's free-form aggregate metrics → markdown narrative | the test hub's reports |
| `release-sprint-predictor` | Gemini 2.5 Flash, 0.2 · "explain why … do not invent" | the forecast's own facts (percentages, dates, slip days), computed without a model → a 2–3 sentence rewording; a written explanation is the fallback | the release hub; a scheduled refresh |
| `replay-narrate` | Gemini 2.5 Flash, 0.4 · "reference people by first name only" | an issue hierarchy's status transitions with the person who made each → a narrative | none (a comment mirrors its constants) |
| `generate-whatsapp-summary` | Gemini 2.5 Flash · ten persona tones; "name items by key and summary"; ≤ 1500 characters | a filter's items (already permission-checked and capped) with counts → a WhatsApp message | the WhatsApp summary feature |
| `presence-backup-suggest` | Gemini 2.5 Flash, JSON · "recommend the best backup assignee" | the absent assignee's name, leave dates and note, colleagues' names → a chosen colleague and a reason | none (a test asserts it is not called) |
| `docex-import` | Gemini 2.5 Flash, the native endpoint with the PDF inline, a JSON schema | a PDF (≤ 10 MB) → a title, the source language, editor blocks, Arabic translated to English | the wiki editor's import |
| `deploy-control` | a second provider's small model, 100 tokens · "one short sentence for a non-technical product owner" | a deployment run's commit message → a sentence, cached per run | the hosting-connection admin page |

None was a false positive: each calls a model.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-042 (the audit)
Capability:      none changed — ledger rows only
Inputs:          none
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged
Budget:          unchanged
Failure mode:    none
Cache:           none
Safety:          two functions sent names or leave notes to a model; neither is carried
Contract:        unchanged
Invariants:      unchanged
Blast radius:    LOCAL — the ledger, a decision, two questions
Decision level:  2 — D-063 (the lead)
ADR:             none
```

## What changed
- **The final states** (`docs/04-ledgers/capabilities.md`):
  - `strata-advisory` → **retired-changed**, `brief`: a briefing per Theme over the chain. The
    scorecard, benefit and value-at-risk facts wait for their modules. The role check, the draft
    kept for a reviewer who is not its author, and the audit row are the backend's.
  - `generate-whatsapp-summary` → **retired-changed**, `summarize` mode `digest`: the backend's
    items and counts. The personas are not carried; the message format and its delivery are the
    backend's.
  - **Dropped:** `release-sprint-predictor` (arithmetic, the backend's), `replay-narrate` (never
    called; names), `presence-backup-suggest` (never called; a person chosen over personal data),
    `deploy-control` (the hosting console).
  - **Deferred**, a state added to the ledger for a function whose product area has not moved:
    `report-insights` (the test reports, `Q-019`) and `docex-import` (the wiki import, `Q-020`).
- **The Retires column** of `brief` and `summarize` names the two they now retire.
- **The count line** reads forty-nine: 24 retired, 13 retired-changed, 10 dropped, 2 deferred. It had read
  "20 retired … 10 dropped" for forty-one, while the table held 24, 11 and 6; counted by name here.
- **`D-063`** (decided by the lead) records the eight states. **`Q-019`** and **`Q-020`** ask whether the test
  report narrative and the PDF import are wanted.

## Eval and budget numbers
No capability changed; no eval set moved.

## Verify
Fast checks: the static gate green (17 checks). No code changed; the full gate runs before this is
pushed. The full gate, on the tree this change is committed from:
```
$ make verify
VERIFY GREEN — GATE GREEN (56 checks) · 1217 passed, coverage 99.42% · EVALS GREEN · selftest 58/58 (on the host, on the final tree)
$ make ci
VERIFY GREEN in catalyst-ai-ci:d06a9811d6b3 — 56 checks · 1217 passed, 99.42% · EVALS GREEN · selftest 58/58 · stamp: tree 853cbf005fc8 at 2026-09-25T11:40:25+00:00 -- green
```

## Decisions and questions
- `D-063` decided by the lead; `Q-019` and `Q-020` answered: deferred until their areas move.
- For the backend: the advisory's draft, reviewer and audit; the release forecast's arithmetic; the
  WhatsApp message and its delivery. Handed over with this change.

## Commit
- `docs(brain): eight more previous functions, each with a final state`
- `gen: the capabilities ledger names the eight`
