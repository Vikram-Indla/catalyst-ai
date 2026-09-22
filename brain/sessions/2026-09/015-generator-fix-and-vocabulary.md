# 015 — two result schemas renamed for the backend's generator; the vocabulary check; six questions answered

**Date:** 2026-09-24 · **Ticket:** AI-015 (follow-up) · **Capability or package:** contract/search (two component names), tools/checks (a new check), the rules, the brain · **Author:** a contributor

## Read
The backend's report on generating its client from the document: `index.upsertDocuments` and
`index.deleteDocuments` make its generator emit wrapper types named after the operations,
which collide with the response schemas `IndexUpsertResponse` / `IndexDeleteResponse`; it
carries an overlay renaming the operation ids meanwhile. Its own gate's check that refuses a
word of a shape the repository never carries, and how it keeps the shapes out of its tree (they
are assembled at run time; the plant is seeded in memory). `RULE-005 §1` and `RULE-006`. The
lead's answers to the six open questions.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-015 (follow-up)
Capability or package: contract/search — IndexUpsertResult, IndexDeleteResult (component names only); tools/checks/vocabulary (+ its in-memory plant);
                 RULE-005 §1 (the rule stated), RULE-006 (two rows: origin, vocabulary); brain/04 (six rows answered)
Inputs:          unchanged
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged
Budget:          unchanged
Failure mode:    a rendered document whose component names collide with a generator's derived names → renamed; a word of a foreign shape in the tree → refused by the gate
Cache:           unchanged
Safety:          unchanged
Contract:        FIX — two component names; no wire change; the backend regenerates and drops its overlay
Invariants:      unchanged
Blast radius:    CONTRACT — two component names in the document (no wire change), one check, two rule pages
Decision level:  1
ADR:             none; RULE-005 1.2.0, RULE-006 1.2.0
```

## Changed
- `contract/search.py` — `IndexUpsertResponse` → `IndexUpsertResult`, `IndexDeleteResponse` → `IndexDeleteResult`; the three search modules and the contract test follow; the document regenerated; a `FIX` entry in the changelog
- `tools/checks/vocabulary.py` — every text file of the repository, every line, against three shapes (the ids of the lead's private planning, the name of its files, the names of its people) assembled at run time; skips only its own source; in the full gate and the fast subset; its plant is a value the self-test builds in memory (48/48)
- `RULE-005 §1` — the rule in words: the repository speaks of "the lead" and "a contributor" and of nothing behind them; `RULE-006` — the rows for `origin` (owed since the previous record) and `vocabulary`
- `brain/04-OPEN-QUESTIONS.md` — Q-012 (later), Q-013 (not before the cutover), Q-014 (dropped), Q-015 (wanted, small), Q-016 (wanted, after the backend's client), Q-017 (the jobs table and the worker are AI-016, next)

## Verify
```
$ make verify
GATE GREEN (46 checks) · oasdiff: no breaking change against main · 761 passed in 131 s · coverage 99 % · fourteen sets EVALS GREEN · pip-audit: no known vulnerabilities · selftest: 48/48 checks red on their plant
VERIFY GREEN
```
```
$ make ci
GATE GREEN (46 checks) · 761 passed · coverage 99 % · EVALS GREEN · selftest: 48/48
VERIFY GREEN
stamp: tree 62e6790b7362 in python:3.12.14-slim at 2026-09-22T09:29:45+00:00 -- green
(this block was written after the stamp; the push's own run re-proves the tree)
```

## Eval and budget numbers
No prompt, pipeline or set moved: the search package changed two class names in its response
models only. The `search` set re-runs unchanged in `make verify` (146 cases: recall_at_10 0.914 (floor 0.85), mrr 0.787 (floor 0.7), tenant_isolation 1.000, provenance_present 1.000, kinds_respected 1.000 — unchanged); no budget line moves.

## Decisions and questions
- None new. The two component names are the document's business; the operation ids the backend already codes against stay.

## Commit
1. Files: `src/catalyst_ai/capabilities/search/**`, `src/catalyst_ai/contract/search.py`, `tests/contract/test_search.py`, `tools/checks/**`, `docs/02-rules/RULE-005-git-and-sessions.md`, `docs/02-rules/RULE-006-enforcement.md`, `docs/04-ledgers/contracts-changelog.md`, `brain/**`
   Proposed: `fix(contract): result schemas the generator can name; the vocabulary check`
2. Files: `api/openapi.yaml`
   Proposed: `gen: contract document with the renamed index result schemas`
Green light: awaited

## Next
AI-016 — the jobs table and the worker as `ADR-007` says, with `verify_stored` before every execution.
