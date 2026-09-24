# 034 — translate keeps a governed glossary

**Date:** 2026-09-24 · **Ticket:** AI-030 · **Capability or package:** translate (contract, descriptor, glossary, quality, pipeline, postprocess, prompt v2), `evals/translate` (set v2, graders, thresholds), tools (the stand-in's glossary, the glossary cases) · **Author:** a contributor

The product's strategy module has a controlled vocabulary: theme, charter, key result, project
card, direct component, the threshold scheme, the role names, the lifecycle states. Its Arabic must
be the same everywhere and stay reviewable. `translate` worked field by field and could choose
different Arabic for the same term; this gives it a glossary it must follow, sent as data.

## Read
`THREAT-002`, `RULE-003` (additive changes), `RULE-008`; the translate contract, pipeline,
postprocess, quality, prompt v1, graders and set; the translation stand-in.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-030
Capability:      translate (v1.0.0 -> v1.1.0, additive)
Inputs:          + glossary[] ≤ 100 {source, target, note?} (default empty)
Tenant boundary: unchanged
Provider/model:  unchanged (text-fast)
Prompt version:  1 -> 2 (the glossary paragraph and field; codes named among the kept spans)
Eval set:        1 -> 2: +10 glossary cases (EN -> AR 6, AR -> EN 4; 2 injection), +3 graders
Budget:          unchanged (p95 cost 427 µ$ of 2 000)
Failure mode:    a term not enforced -> glossary_conflict (ambiguous_glossary | term_not_rendered),
                 the translation still returned, confidence lowered by 0.3; never an error, never a guess
Cache:           unchanged (the glossary is part of the canonical input)
Safety:          the glossary fenced as data; a note is never an instruction
Contract:        CHANGE, additive — oasdiff against main: no breaking changes
Invariants:      INV-075 (new)
Blast radius:    CONTRACT — fields added to the contract (first claimed CAPABILITY; corrected)
Decision level:  2
ADR:             none (D-056)
```

## What changed
- **Contract.** The request gains an optional `glossary` of `{source, target, note?}` entries. The
  response gains `glossary_applied[]` and `glossary_conflict[]` (`{source, reason}`). All default to
  empty, so existing callers are unaffected.
- **The rule, in code** (`capabilities/translate/glossary.py`), checked after the model answers:
  - a source found in the text is reported as applied only when the translation carries its exact
    target;
  - a source the glossary gives two targets is `ambiguous_glossary`, reported and never enforced;
  - a target the translation lacks is `term_not_rendered`, and the translation still comes back.
  - Matching tolerates case, Arabic diacritics and tatweel, alef forms, and the clitics a word takes
    (`وبطاقة المشروع` holds `بطاقة المشروع`).
- **Codes.** Codes such as `TH-STD v3` join the kept spans (keys such as `PC-011` already were), in
  the confidence and in the graders.
- **Prompt v2.** v1 plus one paragraph (render the exact target and never translate a term freely;
  a note is data) and the glossary field.
- **Evals.** 10 cases with the glossary, and three graders at a floor of 1.0: `glossary_kept`,
  `glossary_reported` and `glossary_note_inert`. `no_name_like_introduced` now counts the
  glossary's own targets as known words, since an English target such as "Project Card" is
  capitalised by design. The 94 existing cases are byte-identical.

## Red first
```
the "not rendered" branch planted to count every found term as applied
  test_enforced_terms_are_named_and_the_rest_reported_never_guessed                      FAILED
  test_a_term_the_translation_did_not_render_is_reported_and_costs_confidence            FAILED
the stand-in planted to ignore the glossary
  glossary_kept 0.904, glossary_reported 0.904 (all 10 glossary cases) — EVALS RED
restored: translate v2 104 cases, every grader 1.000, EVALS GREEN
```

## Eval
```
-- translate v2 - 104 cases
   schema_valid 1.000 · target_script 1.000 · detected_language_correct 1.000 · structure_kept 1.000
   spans_kept 1.000 · no_name_like_introduced 1.000 · length_bounds 1.000 · no_forbidden_content 1.000
   glossary_kept 1.000 · glossary_reported 1.000 · glossary_note_inert 1.000 · overall 1.000
   p95 latency 14 ms (budget 6000) · p95 cost 427 micro-dollars (budget 2000)
```
Authored fixtures: the numbers measure the glossary rule, its reporting and the graders, not
translation quality.

## Verify
Fast checks during the loop: the unit, contract and architecture suites, lint, types, the static
gate, the set, oasdiff against main. The full gate at the end of the loop is pasted in record 027.

## Decisions and questions
- `D-056` proposed; `INV-075` added; `THREAT-002` gains the glossary.

## Eval and budget numbers
This change's own numbers are in the record above; the run of every set, with each set's p95
latency and cost against its budget, is in the gate output below.

## The gate at the end of the loop
One full gate proves the whole tree of the loop, every record's change together.
```
$ make verify
(on the workstation, before four records' claims were corrected to CONTRACT — records only)
GATE GREEN (52 checks)
oasdiff: no breaking change against main
TOTAL                                                            7711     27    956     25    99%
1056 passed in 309.82s (0:05:09)
GATE GREEN (1 checks)
EVALS GREEN
GATE GREEN (1 checks)
No known vulnerabilities found
INF no leaks found
GATE GREEN (1 checks)
selftest: 54/54 checks red on their plant
VERIFY GREEN
exit=0 elapsed=628s
```
```
$ make ci
(in catalyst-ai-ci:d06a9811d6b3; the second run — the first was red: 1052 passed, 4 errors in
tests/storage/test_logins.py, SocketConnectBlockedError, fixed as record 031 says)
GATE GREEN (52 checks)
oasdiff: no breaking change against main
TOTAL                                                            7711     27    956     25    99%
1056 passed in 535.13s (0:08:55)
GATE GREEN (1 checks)
EVALS GREEN
GATE GREEN (1 checks)
No known vulnerabilities found
INF no leaks found
GATE GREEN (1 checks)
selftest: 54/54 checks red on their plant
VERIFY GREEN
stamp: tree b51a07c33c09 in catalyst-ai-ci:d06a9811d6b3 at 2026-09-24T12:03:29+00:00 -- green
exit=0 elapsed=1333s
```

## Commit
See the proposal list in record 027.
