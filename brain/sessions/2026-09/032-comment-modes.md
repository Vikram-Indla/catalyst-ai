# 032 — the comment modes of improve-story

**Date:** 2026-09-24 · **Ticket:** AI-028 · **Capability or package:** improve-story (contract, descriptor, pipeline, comments, postprocess, prompt v2), `evals/improve-story` (set v2, graders, thresholds), tools (the stand-in) · **Author:** a contributor

The previous system's `ai-improve-comment` rewrote a comment and suggested a reply. The lead
answered `Q-015`: wanted, small, as two modes of the golden capability rather than a new one.

## Read
`Q-015`, `ARCH-002 §3` (people as tokens), `THREAT-002`, `RULE-008`; the improve-story contract,
pipeline, prompt v1, graders and set; the summaries' participant tokens; the stand-in.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-028
Capability:      improve-story (v1.0.0 -> v1.1.0, additive)
Inputs:          + comment {participant token, text with mentions only as @p<N>} for the two modes
Tenant boundary: unchanged; people only as the backend's tokens
Provider/model:  unchanged (text-default)
Prompt version:  1 -> 2 (the item modes' instructions unchanged; their fixtures move with the text)
Eval set:        1 -> 2: +13 cases (EN and AR, both modes, two injection), +2 graders
Budget:          unchanged (p95 cost 682 µ$ of 2 000)
Failure mode:    a named mention -> refused at the door; markup dropped or someone new named ->
                 ai.output.invalid (markup_dropped, reference_invented)
Cache:           unchanged (the comment is part of the canonical input)
Safety:          the comment fenced as data; two injection cases
Contract:        ADD — two modes, one optional field; the item modes unchanged (changelog)
Invariants:      none new (the token rule is ARCH-002 §3's)
Blast radius:    CONTRACT — two modes and a field added to the contract (first claimed CAPABILITY; corrected)
Decision level:  2
ADR:             none (D-053)
```

## What changed
- **Contract.** Modes `polish_comment` and `reply`, and a field `comment` with the author's token
  and the text. Any `@mention` that is not a token (`@alice`, `@john.smith`) is refused at the
  door, and an email is not read as a mention. The comment modes require `comment`; the item modes
  refuse it. For the comment modes, `improved_description` carries the text and
  `acceptance_criteria` is null.
- **Pipeline.** The comment is a fenced user field, and its author's token is a developer line
  ("Comment by: p2"). After the schema and the leak scan, `comments.markup_problem` refuses a polish
  that dropped any mention, link or code span, and a reply that mentions anyone but the comment's
  author and mentioned, or links anything the comment, the title or the description does not.
- **Prompt v2.** v1 plus one paragraph on tokens and markup, the comment field, and two operation
  blocks. The six item operations are word for word v1's.
- **Evals.** 13 cases: polish EN ×4, AR ×2, injection ×1; reply EN ×3, AR ×2, injection ×1. Two new
  graders: `markup_kept` and `no_new_facts`, both with a floor of 1.0. The graders that compare a
  result with its source read the comment in the comment modes, and a reply owes the comment's
  keys nothing (`identifiers_kept` is 1.0 for a reply). The stand-in answers both modes in
  `tools/authored_comment.py`.

## Red first
```
the pipeline's markup refusal removed
  test_a_comment_mode_breaking_the_markup_rule_is_refused[polish drops markup]      FAILED
  test_a_comment_mode_breaking_the_markup_rule_is_refused[reply names someone new]  FAILED
the stand-in planted to replace mentions with "them"
  markup_kept 0.954 < 1.0 — EVALS RED (the pipeline refuses those cases, so every grader drops)
the first eval run, before the graders learnt the comment modes
  identifiers_kept 0.938, no_new_facts 0.923 — a reply was held to the comment's keys, and a
  token's digit read as a new number; both graders corrected, not loosened
restored: improve-story v2 65 cases, every grader 1.000, EVALS GREEN
```

## Eval
```
-- improve-story v2 - 65 cases
   schema_valid 1.000 · length_bounds 1.000 · language_preserved 1.000 · identifiers_kept 1.000
   no_forbidden_content 1.000 · rationale_present 1.000 · mode_shape 1.000 · markup_kept 1.000
   no_new_facts 1.000 · overall 1.000
   p95 latency 14 ms (budget 4000) · p95 cost 682 micro-dollars (budget 2000)
```
Authored fixtures: the numbers measure the pipeline, the refusals and the graders, not a live model.

## Verify
Fast checks during the loop: the unit, contract and architecture suites, lint, types, the static
gate, the set. The full gate at the end of the loop is pasted in record 027.

## Decisions and questions
- `D-053` proposed; `Q-015` answered and built; `THREAT-002` gains the comment modes.

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
