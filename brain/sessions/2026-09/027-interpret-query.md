# 027 — interpret-query

**Date:** 2026-09-24 · **Ticket:** AI-026 · **Capability or package:** interpret-query (new), contract/interpret_query, evals/interpret-query, tools (authored stand-in, set builder, eval kit), ops/alerts · **Author:** a contributor

A member types "my open defects from last week" into the list view and should get what the query
would have given. The previous system's filter translator was never carried (`Q-016`); the lead
wants it. It is built here as a small sync capability over the filter grammar the backend sends,
as data, so the service holds no copy of the grammar and can never name a field it was not sent.

## Read
`ARCH-003`, `ARCH-004`, `ARCH-008 §1`, `ARCH-009`, `RULE-003`, `RULE-008`; the `unfurl` package as the
pattern; the previous system's query-language field map (read-only reference, nothing copied).

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-026
Capability:      interpret-query (new)                                      (ARCH-003)
Inputs:          text · CONFIDENTIAL; grammar · INTERNAL; now, timezone, locale · PUBLIC (ARCH-002 §3)
Tenant boundary: organization_id scope on the cache and the budget; no storage rows
Provider/model:  gemini · text-fast (thinking minimal)                      (ARCH-005)
Prompt version:  prompt_v1                                                  (RULE-008)
Eval set:        evals/interpret-query v1 · 41 cases · floors in thresholds.yaml (ARCH-007)
Budget:          p95 4 000 ms · p95 2 000 µ$                                (ARCH-008)
Failure mode:    query_not_in_grammar (ai.output.invalid) after one repair; an empty query with the
                 terms unresolved when nothing can be placed               (RULE-003 §2)
Cache:           content key · 600 s                                        (ARCH-008 §3)
Safety:          the sentence fenced as data; injected instructions dropped; the explanation scanned
Contract:        interpret_query.run added; not breaking                    (ARCH-004)
Invariants:      INV-070 (new)
Blast radius:    CONTRACT — a new operation in the contract (first claimed CAPABILITY; corrected)
Decision level:  2
ADR:             none (D-048)
```

## The query, checked before it is returned
`capabilities/interpret_query/grammar.py` parses the query subset (clauses with `= != < > <= >=`,
`in`, `not in`, `is empty`, `is not empty`, `was`, `was not`, `changed`; `and`, `or`, `not`,
parentheses; `order by`) against the grammar in the request. A field must be one the grammar names,
an operator one that field accepts, a value one of its closed set, a function of its type, or a
literal of its type; anything written like a function must be a known one. The parse is written
back canonically (keywords in capitals, the grammar's spelling, `and`/`or` operands and `in` lists
sorted), so equal queries compare equal: the response carries that form and the graders compare
with it. A query outside the grammar gets one repair; still outside, the call is refused with one
`query_not_in_grammar` detail per problem, whose message is the problem kind, never the text.

`now` arrives in the organisation's zone with its offset, and "today" is that date. This host has
no zone database and the service needs none; the set's moment (01:30 on 24 September in Riyadh,
still 23 September in UTC) proves the day read is the organisation's.

## Red first
```
test_grammar (before the function rule): "assignee = openSprints()" accepted as a person's name
  → FAILED: DID NOT RAISE GrammarError; now value_not_allowed: assignee openSprints()
the static gate on the new capability: "operation interpret_query.run is judged by 0 rules"
  → the 4 s latency rules now select it (the check from session 021 caught it)
```

## Changed
- `contract/interpret_query.py` — the request (the sentence, the grammar as data, the moment, the
  zone, the locale) and the response (query, explanation, unresolved, confidence).
- `capabilities/interpret_query/` — descriptor (`text-fast`, 4 s, 2 000 µ$), schema, grammar,
  prompt v1, pipeline (the grammar check and its one repair in stage 6), postprocess (the canonical
  query, confidence), routes.
- `evals/interpret-query/` — 41 cases (30 English, 11 Arabic, 3 injection), five code graders,
  floors, README; `tools/evalsets_query.py` builds the set; `tools/authored_query.py` is the
  stand-in (a phrase matcher; it drops an injected instruction with everything after it).
- `config/settings.py` (`capability_interpret_query`), `app.py`, `tools/evalkit.py`,
  `tools/authored.py`, `tools/evalsets.py`; `ops/alerts.yaml` (the 4 s rules); the changelog, the
  errors ledger, the runbook row, `slos.md`, `Q-016` answered, `D-048`, `INV-070`.
- Generated: `api/openapi.yaml`, the set's fixtures, the capabilities, config and eval-sets ledgers.

## Eval and budget numbers
```
-- interpret-query v1 - 41 cases
   query_parses           1.000  (floor 1.0)
   query_equivalent       1.000  (floor 0.95)
   unresolved_reported    1.000  (floor 1.0)
   injection_inert        1.000  (floor 1.0)
   explanation_language   1.000  (floor 0.95)
   overall                1.000  (floor 0.97)
   p95 latency 16 ms (budget 4000.0)
   p95 cost 480 micro-dollars (budget 2000.0)
EVALS GREEN
```
Authored fixtures: the numbers measure the pipeline, the grammar check, the canonical comparison
and the graders, not a model's reading of a sentence.

## Verify
Fast checks during the loop (the lead's instruction): format, lint and types over `src`, `tools`,
`tests`; the new and touched test modules; the static gate without coverage (every check green but
`sessions`, which asks for this section's pasted runs). The full gate runs once at the end of the
loop and is pasted here:
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

## Decisions and questions
- `D-048` proposed; `INV-070` added; `Q-016` answered and built.

## Proposed commits of the loop (nothing is committed during it)
In four groups, so each can be accepted as a whole; every line is at most 80 characters.

**A — the gate and the pipeline**
1. `build(gate): judge a branch by its highest claim, each record at its commit` — record 035 (`prclass`, `commitclass`, the gate's lists, the selftest)
2. `ci(image): build, gate and push the pipeline's image on a Dockerfile change` — record 025 (the image workflow, `ci_image_job`, `workflow_rows`, the pin check and the `COPY`/`ADD` refusal, `ci-image-push`)
3. `ci(nightly): a nightly in the gate's container, fuzzing what a push cannot` — record 026 (`nightly.yml`, `nightly_job`, the nightly targets, the property tests' counts)
4. `build(gate): run at push what the changed files oblige, by a checked map` — record 028 (`change_map`, `change_gate`, the stamp's manifest and `ci-base`, the Makefile targets, the pre-push hook)
5. `ci(nightly): scan the runtime image every night with a pinned, verified scanner` — record 030 (the scan job, `scan-tools`, the scanner's checksums)

**B — the platform**
6. `feat(providers): tenant text stays in the Kingdom, sent as the workload` — record 029 (residency with the region as configuration, credentials, embedding, the adapter, the settings and `config/deployed.py`, the checks, readiness, `ADR-008`)
7. `gen: provider fixtures re-authored for the regional endpoint` — record 029 (every set's fixtures but the four capabilities' below)
8. `feat(storage): three database logins, and vector required rather than created` — record 031 (the logins and the development-password guard, the pre-flight, `db/provision/`, the pgvector 0.8.1 pin, compose)

**C — the capabilities** (each feature, then its generated files)
9. `feat(interpret-query): a sentence becomes a query in the backend's grammar` — record 027 (with its contract test)
10. `gen: eval set and fixtures for interpret-query` — record 027
11. `feat(improve-story): polish a comment and suggest a reply, people only as tokens` — record 032
12. `gen: improve-story fixtures for prompt v2` — record 032
13. `feat(brief): an executive briefing over the strategy chain, every sentence cited` — record 033
14. `gen: eval set and fixtures for brief` — record 033
15. `feat(translate): keep a governed glossary, report what it cannot enforce` — record 034
16. `gen: contract document for the new operations and fields; translate fixtures` — records 027, 032–034 (`api/openapi.yaml`)

**D — after the first push**
17. `build(ci): pin the pipeline's image to the digest the image workflow printed` — record 025 (after the first push, once the image workflow has printed the digest)

The groups share files (`tools/rules.py`, `tools/checks/ci.py`, the selftest, the gate's list,
the Makefile, the ledgers, `settings.py`, the stand-in); each commit takes its own lines with the
later ones held back, and the tree pushed is the tree the full gate stamped.
