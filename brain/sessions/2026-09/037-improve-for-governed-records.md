# 037 — Improve for governed records: the record as data, its facts kept

**Date:** 2026-09-24 · **Ticket:** AI-032 · **Capability or package:** improve-story (contract, governed rule, pipeline, prompt v3), generate-children (contract, drafts, prompt v2), search (`ids_only`), summarize (set v3), `platform/language` (`latin`, `stated_facts`), `evals/improve-story` v3, `evals/generate-children` v2, `evals/summarize` v3, tools (the cases) · **Author:** a contributor

The product's governed records (charters, objectives, key results, project cards, project
objectives) get the same four Improve actions the previous system offered on every item type:
improve the text, summarise the comments, suggest children, find similar. The previous system ran
the same actions on every type and varied only the prompt's focus per type; here the focus arrives
as data with the record, and the service holds no kind and no rule of the product.

## Read
The previous system's Improve menu and its configuration (the four actions, the same on every
type; a per-type focus map in `ai-improve-story`; the child label per type); `RULE-003`
(additive changes), `RULE-007`; the improve-story, generate-children, search and summarize
contracts, pipelines, stand-ins and sets.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-032
Capability:      improve-story 1.1.0 -> 1.2.0; generate-children 1.0.0 -> 1.1.0; search 1.0.0 -> 1.1.0;
                 summarize unchanged (set only)
Inputs:          improve-story + record {focus, context[], glossary[]}; generate-children + child_focus,
                 draft_only; search + ids_only
Tenant boundary: unchanged (search stays per organisation; ids_only only drops content)
Provider/model:  unchanged (improve text-default; summaries unchanged)
Prompt version:  improve-story 2 -> 3, generate-children 1 -> 2 (sections sent only with a record or
                 draft_only; every other request byte-identical, its fixtures unchanged)
Eval set:        improve-story 2 -> 3 (+15), generate-children 1 -> 2 (+5), summarize 2 -> 3 (+5);
                 +4 graders
Budget:          unchanged
Failure mode:    a record's rewrite adding or dropping a fact or losing a glossary term ->
                 ai.output.invalid (fact_added, fact_lost, glossary_term_lost); a draft stating a new number -> withheld, counted
Cache:           unchanged (the record and the flags are part of the canonical input)
Safety:          the record's focus, context and glossary fenced as data; an instruction in the text
                 to set a target is inert (a case)
Contract:        CHANGE, additive — oasdiff against main: no breaking change, no warning
Invariants:      INV-076, INV-077 (new)
Blast radius:    PLATFORM — `platform/language` gains the shared digit normaliser and fact reader
Decision level:  2
ADR:             none (D-059)
```

## What changed
- **improve-story.** `record` carries the kind's focus, the names around the record and its
  glossary; the kind stays `item_type`. With a record, a developer section states the rule and
  the three texts follow, fenced. After the output is parsed: its digits are made Latin, then
  `governed.problems` compares its facts (numbers read as Latin, item keys, links, participant
  tokens) with the inputs' (title, description, criteria, parent, comment and its author, context).
  The member's hint and the kind's focus are not sources: a hint asking for a 90% target does not
  make 90 a fact. The facts of the text it rewrites must all survive (`fact_lost`): a shorter
  wording that drops a key result's target has changed it. A glossary term the source uses must
  survive exactly. Any problem refuses the output. A measure named without a number (a KPI's
  name alone) is not something a deterministic check can tell from ordinary words; the prompt's
  record rule forbids it, and a live recording is where it can be graded. There is no streaming path in this service's improve-story; the one route runs the guard.
- **generate-children.** `draft_only` and `child_focus`: the drafts section and the focus travel
  only when asked. `drafts.as_drafts` removes criteria, writes Latin digits and withholds a
  candidate stating a number, date or link the parent and the sources lack; the response marks
  each candidate `draft` and counts `withheld`. Sibling de-duplication is unchanged.
- **search.** `ids_only`: hits keep the key, the kind, the score and the provenance; no title, an
  empty snippet. What is linkable stays the backend's.
- **summarize.** Unchanged; five comment threads on governed records join the set.
- **platform/language.** `latin` and `stated_facts` (numbers, item keys, links with digits read as
  Latin), shared by the two new modules. `interpret-query`'s own digit table is left as it is in
  its pending change; moving it to `latin` is a follow-up.
- **Kinds as data.** `test_no_record_kind_is_spelled_in_the_service` greps the source and prompts
  for the kinds' names and the product's module name: none.
- **Evals.** `tools/evalsets_strata.py` writes the cases (improve-story and generate-children keep
  their hand-written lines and replace only `strata-` ones): each kind in English and Arabic,
  Arabic-Indic digits, a link, hints asking for a target, a due date and an owner, an `expand`
  with nothing to measure, an instruction to set a target; key results under an objective and
  objectives under a card as drafts, one repeating a sibling. Graders `record_facts_kept`,
  `glossary_exact`, `latin_digits`, `drafts_only`, floors 1.0. The identifier graders and the
  confidence now read digits as Latin, so `٤٠` in and `40` out is the same number.

## Red first
```
the fact-lost rule disabled (a self-review against "adds or changes", after the first build)
  test_a_shorter_wording_that_drops_the_target_has_changed_it                        FAILED
  (and the two tests that replace 70 with 90, which now also report 70 lost)
the facts guard removed from the pipeline
  test_a_record_run_that_adds_a_target_is_refused                                   FAILED
the output left in its own digits
  latin_digits 0.975 (strata-improve-key_result-ar, strata-improve-project_objective-ar) — EVALS RED
draft_only ignored in drafts.as_drafts
  drafts_only 0.993 (strata-children-project_objective-ar) — EVALS RED
the tests' first run found two defects in the guard, fixed before anything else:
  a participant token's digits (@p2) were read as the number 2; a reply to the comment's own
  author was an "added" participant
restored / fixed: the three sets green, every grader 1.000; the unit and architecture suites pass
```

## Eval
```
-- improve-story v3 - 80 cases
   the v2 graders 1.000 · record_facts_kept 1.000 · glossary_exact 1.000 · latin_digits 1.000
   overall 1.000 · p95 latency 12 ms (budget 4000) · p95 cost 743 micro-dollars (budget 2000)
-- generate-children v2 - 144 cases
   the v1 graders 1.000 · drafts_only 1.000 · overall 1.000 · p95 cost 2180 (budget 6000)
-- summarize v3 - 251 cases
   overall 1.000 · p95 latency 11 ms · p95 cost 1717 micro-dollars (budget 4000)
-- search v1 - 146 cases, unchanged, green
```
Authored fixtures: the numbers measure the guard, the normalisation, the draft rule, the graders
and the stand-in's reading, not a model's writing. The first recording found the leakage scanner
refusing a stand-in output whose closing full stop joined a link at the very end of the text
(`unrequested_url`): its link pattern takes the full stop into the link. A model ending a sentence
after a member's link would be refused the same way, so it is `F-044`, fixed in session 038; the
two project-card cases end on the link again.

## Eval and budget numbers
See `## Eval` above; the full run of every set is pasted with the next full gate.

## Verify
Fast checks in the loop: the unit and architecture suites, lint, types, the four sets, oasdiff
against main (no breaking change, 0 warnings). The contract suite was not in that list, and it
held the one assertion the version bump broke (`test_improve_story`'s `1.1.0`); session 039 ran
it, found it and corrected the expectation to `1.2.0`. The contract suite is in the fast checks
from here on. The full gate (verify, then ci in the image) runs
next; its output is pasted here then.

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
- `D-059` proposed; `INV-076` and `INV-077` added; `F-044` opened (the scanner's link rule).

## Commit — the loop's proposals (nothing is committed during it)
Proposals 1–16 were pushed (`d491ac8..06342f6`); 17 waits for the image workflow's digest.

**E — split under RULE-005 (one ticket, ≤ 400 hand-written lines per commit), in this order**
24. `build(gate): check the commit-size rule — one ticket, 400 lines, gen: only` — record 040
24b. `test(gate): the commit-size check on its limits, tickets, gen: and exceptions`
18a. `feat(interpret-query): take a list's declaration, check the answer against it`
18b. `eval(interpret-query): list-mode cases, graders and pipeline tests`
18c. `docs(interpret-query): record for the list mode` — record 036
19. `fix(gate): the change-aware push's nested make drops the runner's uv path` — record 041
p. `feat(platform): read digits, facts and links the same way everywhere` (records 037, 038)
20a. `feat(improve-story): a governed record's facts kept, or the rewrite refused`
20b. `test(improve-story): the governed rule, its refusals, digits and graders`
20c. `feat(generate-children): draft-only children, no fact the parent lacks`
20d. `feat(search): keys, kinds and scores only, when asked`
20e. `eval(improve): governed-record cases for improve-story, children and summaries`
20f. `docs(improve): record for governed records` — record 037
21. `fix(safety): read a link as written, not with the full stop after it` — record 038
22a. `feat(translate): the drafts contract and the per-item job, machine drafts only`
22b. `feat(translate): submit drafts as a signed job; the worker runs them`
22c. `eval(translate): an English-to-Arabic drafts set over record fields`
22d. `docs(translate): record for the drafts job` — record 039
l. `docs: the loop's decisions, invariants, findings, changelog and status`
23. `gen: contract document, generated ledgers and fixtures for the loop`

**D — after the first push**
17. `build(ci): pin the pipeline's image to the digest the image workflow printed` — record 025

A file two tickets share is committed whole with the first that needs it; the tree pushed is the
tree the full gate stamped.
