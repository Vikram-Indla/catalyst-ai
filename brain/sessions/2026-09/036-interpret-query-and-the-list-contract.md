# 036 — interpret-query speaks the list contract; the change-aware push on Windows

**Date:** 2026-09-24 · **Ticket:** AI-031 · **Capability or package:** interpret-query (contract, descriptor, listing, schema, pipeline, postprocess, prompt v2), `evals/interpret-query` (set v2, graders, thresholds), tools (the listing stand-in and cases) · **Author:** a contributor

The backend's lists now declare what they accept, and refuse anything else; the sentence a
member types must become something a list accepts on the first try. (The change-aware push's
Windows defect found at the same push, F-043, is record 041.)

## Read
The backend's list contract as announced (`limit`, `cursor`, `sort` with a `-` prefix, one
comparison per filter, a range as `<field>From` / `<field>To`); `RULE-003` (additive changes); the
interpret-query contract, pipeline, prompt, stand-in and set; `tools/change_gate.py`, the Makefile,
`.githooks/pre-push`.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-031
Capability:      interpret-query (v1.0.0 -> v1.1.0, additive)
Inputs:          + listing {filters[{param, type, values?}], sorts[], q}; grammar now optional, one of two
Tenant boundary: unchanged
Provider/model:  unchanged (text-fast)
Prompt version:  1 -> 2 (the list mode paragraph and its developer section; the grammar mode unchanged)
Eval set:        1 -> 2: +11 list cases (EN and AR), +3 graders
Budget:          unchanged (p95 cost 480 µ$ of 2 000)
Failure mode:    a parameter, value or sort the list does not declare -> one repair, then
                 ai.output.invalid (parameters_not_declared); never a neighbour
Cache:           unchanged (the declaration is part of the canonical input)
Safety:          the sentence fenced as data; nothing about any list held in the service
Contract:        CHANGE, additive — oasdiff against main: no breaking change, no warning
Invariants:      INV-070 widened to the declaration
Blast radius:    CONTRACT — an operation's request and response gain fields
Decision level:  2
ADR:             none (D-058)
```

## What changed
- **Contract.** `listing` is the list's declaration as the list contract serves it: parameters
  (name, type, closed values), sorts (the first is the default) and whether it has search. `grammar`
  becomes optional, and a request carries exactly one of the two. Both are published as plain
  optional references (`SkipJsonSchema[None]`): the first build published `grammar` as a nullable
  union, which oasdiff flagged as removed properties (a warning), and a generated client would have
  changed. The response gains `parameters` and `sort`.
- **The rule** (`capabilities/interpret_query/listing.py`): the answer is first normalised — digits
  made Latin, whatever their script; an enum value given its declared spelling — and then checked:
  a declared name, a value of its type (`YYYY-MM-DD`, RFC 3339 with an offset, digits, a declared
  value), `q` only where the list has search, a declared sort. A problem means one repair, then a
  refusal, as the grammar mode does. Nothing about any list is in the service: grepping the
  capability and its contract for the three lists' names finds nothing.
- **Prompt v2.** v1 plus the list-mode paragraph and a `developer:listing` section. The grammar
  mode's text is unchanged.
- **Evals.** 11 list cases, STRATA's lists as the contract serves them today plus cycles with a
  start-date range: states, sorts, "by budget" (undeclared), a date on a list with no range
  (unresolved, since the list cannot filter on it yet), and Arabic with Arabic-Indic digits that
  come back Latin. Three graders at a floor of 1.0: `parameters_declared`, `parameters_expected`,
  `latin_digits`. The 41 grammar cases are byte-identical.

## Red first
```
the list check removed from the pipeline
  test_an_undeclared_parameter_gets_one_repair_then_a_refusal                        FAILED
the stand-in planted to read "by budget" as state=active (a neighbour)
  unresolved_reported 0.962, parameters_expected 0.962 (list-en-by-budget, list-ar-by-budget) — EVALS RED
restored: interpret-query v2 52 cases, every grader 1.000, EVALS GREEN
```

## Eval
```
-- interpret-query v2 - 52 cases
   query_parses 1.000 · query_equivalent 1.000 · unresolved_reported 1.000 · injection_inert 1.000
   explanation_language 1.000 · parameters_declared 1.000 · parameters_expected 1.000 · latin_digits 1.000
   overall 1.000 · p95 latency 40 ms (budget 4000) · p95 cost 480 micro-dollars (budget 2000)
```
Authored fixtures: the numbers measure the declaration check, its normalisation, the reporting and
the graders, not the model's reading.

## Eval and budget numbers
See `## Eval` above; the full run of every set is pasted with the next full gate.

## Verify
Fast checks in the loop: the unit, contract and architecture suites, lint, types, the static gate,
the set, oasdiff against main. The full gate (verify, then ci in the image) runs next; its
output is pasted here then.

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
- `D-058` proposed; `INV-070` widened.

## Commit
Proposals 18a–c of the loop's list in record 037 (the generated files join its `gen:` commit):
- `feat(interpret-query): take a list's declaration, check the answer against it`
- `eval(interpret-query): list-mode cases, graders and pipeline tests`
- `docs(interpret-query): record for the list mode`
