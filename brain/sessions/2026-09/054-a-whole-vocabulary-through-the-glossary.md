# 054 — A whole strategy vocabulary through the glossary, and terms matched as whole words

**Date:** 2026-09-25 · **Ticket:** AI-041 (F-048) · **Capability or package:** `capabilities/translate/glossary.py`, `tools/authored_glossary.py` (the stand-in), the translate fixtures (re-recorded, authored), `tests/unit/capabilities/translate/strata_glossary.py` (new fixture), `test_strata_glossary.py`, `test_glossary.py` · **Author:** a contributor

This change runs a proposed vocabulary of the strategy module through the glossary rule: 67 terms,
31 of them with a second plausible Arabic rendering. The fixture is test data only; the real
glossary stays data the backend holds. Every Arabic target in it is an unreviewed machine draft.
The first run failed: `F-048`.

## Read
- `glossary.enforce` found a source by substring. So "Objective" was found inside "Project
  Objective", and its target «الهدف» was then required where «هدف المشروع» was right. The same
  happened with "KPI" in "Strategic KPI", "Risk" in "At risk", "Admin" in "STRATA Admin", and
  "Period" in "periodic".
- A miss is reported, never refused (`term_not_rendered`, a confidence penalty; an `unresolved`
  line in a draft). So the cost was noise for the reviewer, not a wrong draft.
- The stand-in swapped a term out of «وبطاقة المشروع» and left the «و» glued to the target:
  `wProject Card`. The substring check had accepted that.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-041 (F-048)
Capability:      translate (translate.run, translate.drafts_job) — the glossary check only
Inputs:          unchanged
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged (v2)
Eval set:        unchanged cases; one authored fixture re-recorded (the stand-in's spacing)
Budget:          unchanged
Failure mode:    fewer false conflicts; no term newly enforced that was not named
Cache:           unchanged (the check runs after the call)
Safety:          INV-075 unchanged: a term is never guessed, ambiguity always reported
Contract:        unchanged
Invariants:      INV-075, INV-078 hold
Blast radius:    CAPABILITY — translate's glossary check, the stand-in, tests
Decision level:  1
ADR:             none
```

## What changed
- **`glossary.py`**:
  - A term matches as whole words: no Latin letter or digit may touch either end, and the Latin
    plural (`s`, `es`) still counts.
  - `named()` takes the longest source first and consumes each match, so a term inside a longer
    one is not checked again.
  - The contracted article is read as the article (`لل` → `لال`). Arabic clitics before a term
    still match.
- **The stand-in** sets a clitic apart from the term it replaces (`w Project Card`). It was
  re-recorded, authored: one fixture changed, `glossary-ar-en-inflected`.
- **The fixture**: 67 terms, 31 with an alternative, sent as one glossary of 98 entries (the limit
  is 100). Each term has one sentence and a stand-in rendering.
- **The tests**:
  - each of the 36 settled terms is enforced exactly, and reported `term_not_rendered` when the
    rendering lacks it;
  - each of the 31 flagged terms is reported `ambiguous_glossary` whichever rendering was chosen;
  - four module sentences enforce each term once;
  - the drafts job drafts all 67 as `machine_draft`, with the flagged terms in `unresolved`.

  `test_glossary.py` gains the whole-word, plural, contracted-article and longest-first cases.

## Red first
```
the fixture on the substring matcher: 4 failed, 1 passed
  (Strategic KPI: KPI ambiguous; Threshold scheme: Threshold too; Objective term_not_rendered;
   drafts: unresolved "ambiguous_glossary: KPI")
the whole-word matcher, before the stand-in fix
  translate eval: glossary-ar-en-inflected glossary_kept=0.00 (the stand-in's "wProject Card")
restored: translate tests 47 passed; translate eval 1.000, translate-drafts eval 1.000
```

## Eval and budget numbers
`translate` v2: `overall 1.000` (floor 0.97). `translate-drafts` v1: `overall 1.000` (floor 1.0).
No case changed, and no budget moved.

## Verify
Fast checks: `make verify-fast` green. The full gate, on the tree this change is committed from:
```
$ make verify
VERIFY GREEN — GATE GREEN (56 checks) · 1189 passed, coverage 99.41% · EVALS GREEN · selftest 58/58 (on the host, before record 043's make hooks fix)
$ make ci
VERIFY GREEN in catalyst-ai-ci:d06a9811d6b3 — 56 checks · 1189 passed, 99.41% · EVALS GREEN · selftest 58/58 · stamp: tree f777f5806cb3 at 2026-09-25T07:16:19+00:00 -- green
```

## Decisions and questions
- A reviewed glossary may want plural and construct forms («المحاور», «بطاقات المشروع»); an
  optional `forms` list per entry is the next step if the review asks for it. Not built.

## Commit
- `fix(translate): a glossary term is a whole word, checked once, the longest first`
- `gen: re-record the translate stand-in` (the fixture and the manifest)
