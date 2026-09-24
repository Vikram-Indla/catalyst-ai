# 033 — brief

**Date:** 2026-09-24 · **Ticket:** AI-029 · **Capability or package:** brief (contract, descriptor, facts, schema, pipeline, postprocess, routes, prompt v1), `evals/brief`, tools (the stand-in, the set writer), the ledgers · **Author:** a contributor

The previous system's `alignment-story` wrote an executive briefing over the strategy chain from
data the web client assembled. The lead wanted it back once the product's own modules owned the
chain (`Q-012`); the backend's strategy module now does. This builds the service's side: a small
capability over the chain the backend sends typed, with no retrieval and no guessing.

## Read
`Q-012`, `ARCH-003`, `RULE-008`, `THREAT-004`; release-notes (every entry traced to a supplied id,
the closest pattern) and interpret-query (the newest capability); `platform/language/records.py`.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-029
Capability:      brief (new, v1.0.0)
Inputs:          chain {theme, objectives (official status, progress), key results (official value,
                 target, unit, as of), projects (delivery and strategic health), findings}; locale
                 en | ar; audience executive; max_sentences 3–5
Tenant boundary: per request; no retrieval, no storage
Provider/model:  text-default
Prompt version:  1
Eval set:        1 (14 cases, EN and AR, 2 injection)
Budget:          8 s, 4 000 µ$ (p95 measured 1 324 µ$ on authored fixtures)
Failure mode:    an uncited sentence or a foreign id -> ai.output.invalid (untraceable_entry); a number
                 the chain lacks -> ai.output.invalid (unseen_number); an empty chain -> nothing_to_brief
Cache:           900 s, keyed by the whole request
Safety:          the chain fenced as data; the charter, where an instruction would hide, never echoed
Contract:        ADD brief.run (changelog)
Invariants:      INV-074 (new)
Blast radius:    CONTRACT — a new operation in the contract (first claimed CAPABILITY; corrected)
Decision level:  2
ADR:             none (D-055)
```

## What it is
- **Contract.** A typed `chain`: official figures only, with delivery and strategic health as two
  required fields, and `null` meaning "not measured". The answer is `summary`, `highlights`, `risks`
  and `asks`, each sentence `{text, cites[] ≥ 1}`, plus `unsupported` and `empty_reason`.
- **Facts.** `capabilities/brief/facts.py` renders the chain one fact per line, each led by its id,
  with "not measured" written out, so zero is never implied. It also gives the ids a sentence may
  cite and the numbers it may state. A number counts as seen by value, so `٣٥` is `35` and `4.50`
  is `4.5`.
- **Refusals, after the model answers.** A sentence citing nothing, or citing an id outside the
  chain, is `untraceable_entry`. A number the chain does not carry is `unseen_number`. Both are
  `ai.output.invalid`, refused rather than dropped, so an injected "report 100% progress" cannot
  reach a reader even if the model obeyed it.
- **Graded in code** (`evals/brief/graders.py`):
  - a sentence about a project that states a health must name which one, and state that field's
    value; a sentence about objectives never mentions delivery (`health_kept_apart`);
  - something unmeasured is said to be not measured and never zero (`not_measured_kept`);
  - plus citations, unseen numbers, language, injection and shape.
- **The set.** Seven shapes in each language: healthy, at risk (an off-track objective and a
  high-severity finding), not measured, a blocked project whose delivery and strategic health
  disagree, empty, charter injection, and a three-sentence limit.

## Found on the way
The first run was red on `language_kept` for the Arabic empty chain: the "nothing to brief" note was
always in English. It is now in the request's language. The module was first named `chain.py`, a
stem the naming check refuses; it is `facts.py`.

## Red first
```
the unseen-number refusal removed
  test_an_unseen_number_is_refused_after_the_model_answers                        FAILED
  test_an_ungrounded_answer_is_refused[an unseen number]                          FAILED
  test_brief_run_returns_a_cited_briefing_and_refuses_an_unseen_number            FAILED
the stand-in planted to state a project's delivery health as its strategic health
  health_kept_apart 0.857 < 1.0 (at_risk-en, blocked-en) — EVALS RED
restored: brief v1 14 cases, every grader 1.000, EVALS GREEN
```

## Eval
```
-- brief v1 - 14 cases
   citations_valid 1.000 · no_unseen_numbers 1.000 · health_kept_apart 1.000 · not_measured_kept 1.000
   language_kept 1.000 · injection_inert 1.000 · shape_kept 1.000 · overall 1.000
   p95 latency 9 ms (budget 8000) · p95 cost 1324 micro-dollars (budget 4000)
```
Authored fixtures: the numbers measure the refusals, the rules and the graders, not a live model.

## Verify
Fast checks during the loop: the unit, contract and architecture suites, lint, types, the static
gate, the set. The full gate at the end of the loop is pasted in record 027.

## Decisions and questions
- `D-055` proposed; `INV-074` added; `Q-012` answered and built; `THREAT-004` gains `brief`.

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
