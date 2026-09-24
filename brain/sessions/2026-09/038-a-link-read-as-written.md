# 038 — A link read as written: the full stop after it ends the sentence, not the link

**Date:** 2026-09-24 · **Ticket:** AI-033 (F-044) · **Capability or package:** `platform/language` (`links`), `platform/safety/output.py`, `capabilities/improve_story/comments.py`, tools (the governed-record cases) · **Author:** a contributor

Recording the governed-record cases (session 037) found the leakage scanner refusing an output
that ended a sentence right after the member's own link: its pattern took the full stop into the
link, and `…/permits.` is in no input. A model will write that sentence. The rule was right; the
reading was wrong, and two more copies of the same pattern (the governed-record fact reader and
the comment markup check) had the same defect.

## Read
`F-044`; `platform/safety/output.py` and its tests; `INV-035`; `ARCH-009 §3`; `RULE-000 §6–7`;
the other link patterns in the service (`capabilities/improve_story/comments.py`,
`platform/language/signals.py`, `capabilities/translate/quality.py`).

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-033 (F-044)
Capability:      none changed in version; the scanner every capability runs, the fact reader of
                 improve-story's governed records, its comment markup check
Inputs:          unchanged
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged in cases; the two project-card cases of improve-story v3 end on the
                 member's link again (the form that was refused)
Budget:          unchanged
Failure mode:    fewer false `ai.output.unsafe` (unrequested_url); a link the inputs lack is still
                 refused, punctuated or bracketed
Cache:           unchanged
Safety:          the scanner's rule unchanged; its reading of a link corrected on both sides
Contract:        unchanged
Invariants:      INV-035 (wording and enforcement named)
Blast radius:    SYSTEM — `platform/safety`
Decision level:  1 — the baseline's rule is unchanged; D-060 records it in case the lead reads the
                 link reading as part of RULE-000 §6.9
ADR:             none (D-060)
```

## What changed
- **`platform/language.links`** — one reader: `https?://` up to whitespace, `<`, `>` or `"`; then
  trailing `.` `,` `;` `:` `!` `?` `'` `*` and the Arabic `،` `؛` `؟` `۔` are removed, and a closing
  `)` or `]` only when the link did not open it (`…/Mercury_(planet)` keeps its bracket;
  `(see …/a)` and `[text](…/a)` read `…/a`). `stated_facts` uses it.
- **The scanner** compares `links(completion)` with the union of `links(text)` over the inputs: the
  same reading on both sides, so nothing the member wrote is foreign and nothing new is admitted.
- **The comment markup check** (`polish_comment` keeps every link; `reply` links nothing new)
  reads links the same way.
- `capabilities/translate/quality.py` keeps its own pattern: there it marks spans the translation
  must keep verbatim. A trailing full stop caught in a span can only lower the deterministic
  confidence when the translation ends the sentence with another mark; it never refuses. Left for
  its own ticket, named in the outbox.

## Red first
```
14 cases of a member's own link ending a sentence or inside a bracket, EN and AR
  10 FAILED (". , ; ? ! :" and "، ؟ ؛ ۔" after the link — each refused as unrequested_url)
   4 passed already (the bracketed forms: the old pattern cut both sides at the bracket alike)
6 cases of an unrequested link, punctuated, bracketed, a path under the member's link, another
  bracketed page: all refused before and after
a widening plant (links cut to their host)
  test_an_unrequested_link_is_refused_whatever_follows_it[…/permits/more.]            FAILED
  test_an_unrequested_link_is_refused_whatever_follows_it[…/Mercury_(element).]       FAILED
the fact reader's own test had the defect baked in (`https://x.example.` as the added link);
  corrected to the link as written
after: the unit and architecture suites pass (976), every eval set green
```

## Eval
```
-- improve-story v3 - 80 cases: every grader 1.000; the two project-card cases end on the
   member's link and are recorded without a refusal
-- every other set: unchanged, green
```

## Eval and budget numbers
See `## Eval` above; the full run of every set is pasted with the next full gate.

## Verify
Fast checks in the loop: the unit and architecture suites, lint, types, every eval set. The full
gate (verify, then ci in the image) runs next; its output is pasted here then.

The full gate on the tree this change is committed from:
```
$ make verify
(ran before the one-line hermeticity fix to tests/unit/tools/test_commitsize.py that record
040 names; make ci below ran on the final code, that fix included)
582 files already formatted
All checks passed!
Success: no issues found in 582 source files
Contracts: 5 kept, 0 broken.
GATE GREEN (53 checks)
api\openapi.yaml matches the app
oasdiff: no breaking change against main
TOTAL                                                            8129     29   1030     25    99%
1137 passed in 177.40s (0:02:57)
GATE GREEN (1 checks)
-- assistant v1 - 83 cases
-- brief v1 - 14 cases
-- documents v1 - 92 cases
-- documents-generate v1 - 42 cases
-- documents-ingest v1 - 19 cases
-- generate-children v2 - 144 cases
-- generate-tests v1 - 89 cases
-- improve-story v3 - 80 cases
-- interpret-query v2 - 52 cases
-- post-mortem v1 - 45 cases
-- propose-workflow v1 - 46 cases
-- release-notes v1 - 90 cases
-- search v1 - 146 cases
-- summarize v3 - 251 cases
-- translate v2 - 104 cases
-- translate-drafts v1 - 9 cases
-- unfurl v1 - 6 cases
EVALS GREEN
GATE GREEN (1 checks)
No known vulnerabilities found
9:30PM INF no leaks found
GATE GREEN (1 checks)
selftest: 55/55 checks red on their plant
VERIFY GREEN
verify exit 0
$ make ci
582 files already formatted
All checks passed!
Success: no issues found in 582 source files
Contracts: 5 kept, 0 broken.
GATE GREEN (53 checks)
api/openapi.yaml matches the app
oasdiff: no breaking change against main
TOTAL                                                            8129     29   1030     25    99%
1137 passed in 311.22s (0:05:11)
GATE GREEN (1 checks)
-- assistant v1 - 83 cases
-- brief v1 - 14 cases
-- documents v1 - 92 cases
-- documents-generate v1 - 42 cases
-- documents-ingest v1 - 19 cases
-- generate-children v2 - 144 cases
-- generate-tests v1 - 89 cases
-- improve-story v3 - 80 cases
-- interpret-query v2 - 52 cases
-- post-mortem v1 - 45 cases
-- propose-workflow v1 - 46 cases
-- release-notes v1 - 90 cases
-- search v1 - 146 cases
-- summarize v3 - 251 cases
-- translate v2 - 104 cases
-- translate-drafts v1 - 9 cases
-- unfurl v1 - 6 cases
EVALS GREEN
GATE GREEN (1 checks)
No known vulnerabilities found
5:16PM INF no leaks found
GATE GREEN (1 checks)
selftest: 55/55 checks red on their plant
VERIFY GREEN
stamp: tree a68be55f2c88 in catalyst-ai-ci:d06a9811d6b3 at 2026-09-24T17:16:36+00:00 -- green
ci exit 0
```

## Decisions and questions
- `F-044` closed; `D-060` proposed; `INV-035` reworded.

## Commit
Proposal 21 of the loop's list in record 037:
- `fix(safety): read a link as written, not with the full stop after it`
