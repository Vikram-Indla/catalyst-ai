# 039 — Arabic drafts for seeded records: a job, machine drafts only, every item keyed

**Date:** 2026-09-24 · **Ticket:** AI-034 · **Capability or package:** translate (the drafts job: `drafts.py`, `jobs.py`, a route), `contract/translate_drafts.py`, `platform/httpserver` (a job's result published), `app.py` (the runner), `evals/translate-drafts` v1, tools (the cases) · **Author:** a contributor

The seeded records arrive mostly in English and the product must work fully in Arabic, while no
one on the team reads Arabic. So the Arabic side starts as machine drafts that can never pass for
reviewed text, produced in batches large enough for a seeding run and robust to a budget or an
outage.

## Read
`ADR-007` (the job model) and `platform/jobs`; the documents ingest job (the pattern this
follows); the translate pipeline, glossary and stand-in; `INV-028`; `RULE-003`; the budgets.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-034
Capability:      translate 1.1.0 -> 1.2.0 (a new operation, a job)
Inputs:          DraftsRequest {items[1..200] {record_ref, field, en}, glossary[], glossary_version}
Tenant boundary: unchanged (the job row, the cache and every item carry the organisation)
Provider/model:  unchanged (text-fast, the translate prompt v2, per item)
Prompt version:  unchanged
Eval set:        new: translate-drafts v1 (9 batches, 24 items)
Budget:          per item, the translate door's cap; a batch's p95 is the sum of its items
Failure mode:    per item — empty: skipped; refused (ai.output.invalid, unsafe, rejected): skipped
                 with its code; budget, provider or 80% of the job window: the rest `remaining`
Cache:           the item's key is the pipeline's idempotency key (tenant cache, translate TTL)
Safety:          the door over every item at submission (RESTRICTED refused before storage); the
                 English fenced as data per item; the output scanner per item; an injection case
Contract:        CHANGE, additive — translate.drafts_job; oasdiff against main: no breaking change
Invariants:      INV-078 (new); INV-028 (the job row) unchanged
Blast radius:    PLATFORM — `platform/httpserver` publishes a job's result schema
Decision level:  2
ADR:             none (D-061; the job model is ADR-007's)
```

## What changed
- **The contract** (`contract/translate_drafts.py`): the request as above; the result `drafts[]`
  (`key`, `record_ref`, `field`, `ar`, `status: "machine_draft"` — the only value the `Literal`
  allows — `glossary_hits`, `unresolved`), `skipped[]`, `remaining[]`, `progress`.
- **The job** (`capabilities/translate/drafts.py`): items in order; each through the translate
  pipeline English → Arabic with the batch's glossary and its key as the idempotency key; the
  draft's digits made Latin; `unresolved` carries the glossary's conflicts and every number,
  date, key or link the draft drops or adds — reported, not refused, because a reviewer reads it.
- **Submission** (`capabilities/translate/jobs.py`): the translate door over every item, then the
  platform's `submit` (the envelope must carry a job window); the worker's runner parses the
  stored payload as the request. `app.job_runners` names it.
- **The contract document**: a `:jobs` operation answers `202`; its result appears in `jobs.get`
  as an object. `platform/httpserver.with_job_results` adds the result's schema to the components
  and points the operation at it (`x-job-result`), so the backend can generate the type.
- **Idempotency, honestly.** The key covers record, field, text hash and glossary version, and a
  resubmitted key is answered from the tenant cache — while the cache holds it: in-process, per
  worker, for the translate TTL. The backend stores drafts by key and is the record of what was
  drafted; the announcement says not to resubmit held keys.

## Red first
```
whitespace treated as text      -> drafts-empty-fields, drafts-all-empty raised; EVALS RED (0.778)
the glossary's conflicts dropped -> drafts-ambiguous-glossary glossary_exact 0.00; EVALS RED
the key without the glossary version
  test_the_key_is_the_record_the_field_the_text_and_the_glossary_version            FAILED
  test_a_resubmitted_batch_drafts_only_what_changed                                  FAILED
the draft left in its own digits
  test_a_draft_is_latin_in_digits_marked_machine_and_reports_what_it_dropped         FAILED
restored: every test passes, the set green
```
The tests cover the budget stop, the provider stop, the time stop (a clock the provider moves),
a refused item with its code, an empty field without a call, a resubmission answered from the
cache, the door refusing a batch with a `RESTRICTED` text, the runner over a stored payload, and
the job end to end (signed submit, worker, poll, the result).

## Eval
```
-- translate-drafts v1 - 9 cases
   machine_draft_only 1.000 · keys_and_counts 1.000 · empty_skipped 1.000 · target_script 1.000
   latin_digits 1.000 · glossary_exact 1.000 · facts_kept_or_reported 1.000 · no_forbidden_content 1.000
   overall 1.000 · p95 latency 75 ms (budget 30000, per batch) · p95 cost 877 micro-dollars (budget 10000)
-- every other set: green (translate v2 unchanged)
```
Authored fixtures: the stand-in maps words into the target script and keeps codes, links, keys
and digits. The numbers measure the job's keys, empties, glossary check, fact report and digits,
not a model's Arabic; that is the live recording's work, and a reviewer's.

## Eval and budget numbers
See `## Eval` above; the full run of every set is pasted with the next full gate.

## Verify
Fast checks in the loop: the unit, contract and architecture suites (1 117), lint, types, the
static gate (red only at `sessions`), every eval set, oasdiff against main.

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
- `D-061` proposed; `INV-078` added.
- The change size: `RULE-005 §1` allows ≤ 400 hand-written lines per commit; this ticket is about
  1 000. The split waits for the lead's answer on the loop's commits.

## Commit
Proposal 22 of the loop's list in record 037:
- `feat(translate): Arabic drafts of record fields as a job, never reviewed`
