# 013 — the retirement pass: every previous function and table accounted for

**Date:** 2026-09-23 · **Ticket:** AI-011 · **Capability or package:** docs/04-ledgers (capabilities, legacy-ai-tables, README), brain · **Author:** a contributor

## Read
The capabilities ledger as it stood after AI-010 (two rows still waiting — `improve-comment`,
`interpret-query`; two functions never named — `alignment-story`, `voice-transcribe`); every
record 001–012; the previous system's function listing (forty-one assisted functions, read for
behaviour where the ledger had none: an executive briefing over a strategy chain; audio
transcription through a second provider) and its migrations (a case-insensitive grep for
`create table … ai_` → forty-six tables, three of them missed by the upper-case grep the card's
count came from; twenty-seven `kb_*` and two `tm_ai_*` beside them), with what wrote to each
table (the functions, or the web client alone, or nothing).

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-011
Capability or package: docs/04-ledgers/capabilities.md (the final-states section, the two rows, the retired ideas), a new
                 docs/04-ledgers/legacy-ai-tables.md, the ledgers index; brain (F-024, F-025, Q-012..Q-016, the status)
Inputs:          none (no code)
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged (fourteen sets, authored)
Budget:          unchanged
Failure mode:    a behaviour silently lost → every function has a state and every not-carried behaviour a Q-
Cache:           unchanged
Safety:          unchanged; the tables page states that no product table is read or migrated as it stands (ARCH-002)
Contract:        unchanged
Invariants:      unchanged
Blast radius:    LOCAL — ledgers and the brain
Decision level:  1
ADR:             none
```

## Changed
- `docs/04-ledgers/capabilities.md` — the states line (no row waits to be built; evidence `authored` | `recorded`); `improve-comment` and `interpret-query` dropped with their questions; the retired-ideas rows name `_shared/docx.ts`, `_shared/pptx.ts`, `_shared/docintel.ts` and the page that replaced each; the tables row points at the new page; a final section — every one of the forty-one previous functions with `retired` (the capability, version, set), `retired-changed` (plus the decision) or `dropped` (the reason, the `Q-`), evidence `authored` on every retired row until the live recording
- `docs/04-ledgers/legacy-ai-tables.md` — forty-six `ai_*` tables: 4 to this service (`ai_document_chunks`, `ai_document_embeddings` → the retrieval pair; `ai_agent_runs`, `ai_usage_log` → `provider_calls`), 7 to the backend (`ai_documents`, `ai_document_versions`, `ai_artifact_citations`, `ai_generated_artifacts`, `ai_feedback`, `ai_summary_feedback`, `ai_generated_work_items`), 35 dropped with a reason each; the `kb_*` and `tm_ai_*` note
- `docs/04-ledgers/README.md` — the new page listed
- `brain/`: F-024 (forty-six, not forty-three), F-025 (forty-one, not thirty-nine), Q-012 (the strategy briefing), Q-013 (voice), Q-014 (the assist approval flow), Q-015 (comment polishing), Q-016 (query interpretation); the status

## Verify
```
$ make verify
GATE GREEN (44 checks) · 702 passed in 106 s · coverage 99 % (floor 90) · fourteen sets green · selftest: 46/46 checks red on their plant
VERIFY GREEN
```
```
$ make ci
GATE GREEN (44 checks) · 702 passed · coverage 99 % · fourteen sets green · selftest: 46/46 checks red on their plant
VERIFY GREEN
stamp: tree 83e9d012858b in python:3.12.14-slim at 2026-09-21T19:03:44+00:00 -- green
(the stamp was written before this block was; the push's own run re-proves the tree with it)
```
`grep -c planned docs/04-ledgers/capabilities.md` → 0 · the tables page's rows against the migrations grep → 46 = 46 · forty-one functions: 20 retired, 11 retired-changed, 10 dropped.

## Decisions and questions
- No new decision: a mapping gap is a question, never a build (the card's rule). Q-012..Q-016 to the lead and the product; the backend acknowledges its seven tables in its own outbox.
- F-024, F-025: the counts the card carried were an upper-case grep and a ledger that had never named two functions; the page and the section carry the true counts and say why they differ.

## Commit
1. Files: `docs/04-ledgers/{capabilities,legacy-ai-tables,README}.md`, `brain/**`
   Proposed: `docs(ledgers): the retirement pass, every function and table accounted for`
Green light: given

## Next
The backend's acknowledgement; the lead's answers to Q-011..Q-016; the live recording when the key arrives.
