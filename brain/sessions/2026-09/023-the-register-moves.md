# 023 — the register moves

**Date:** 2026-09-23 · **Ticket:** AI-019 (second part) · **Capability or package:** providers/gemini (the register), contract/models (the alias vocabulary), config, tools (the stand-in, the models check), every text set's fixtures · **Author:** a contributor

The 2.5 text rows refuse a key created now (`F-034`). This session moves the register to the one
stable 3.x text model the key reaches, makes the long-context class unavailable rather than fill
it with a preview, re-generates every text set's fixtures, re-runs every set, and moves the grader
last in its own change.

## Read
`ARCH-005 §2`, `ARCH-008 §1`, `ARCH-007`, `RULE-008 §3`, `ADR-004`; `providers/gemini/{models,aliases}.py`,
`contract/models.py`, `tools/checks/models`, every `evals/*/thresholds.yaml`; the provider's models,
model, pricing, rate-limit and thinking pages (read 2026-09-23).

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-019 (second part)
Capability:      none changed; every text capability resolves to a new model
Inputs:          none
Tenant boundary: unchanged; spend is priced at the new row
Provider/model:  text-default, text-fast → gemini-3.6-flash (thinking minimal); text-long unavailable;
                 embed-default unchanged; grader-default → gemini-3.6-flash, its own change
Prompt version:  unchanged
Eval set:        every text set re-run on re-generated authored fixtures; thresholds unchanged
Budget:          every descriptor holds at today's price; generate-tests over at the 2027 price (D-043)
Failure mode:    text-long refused at settings load; a moving or preview id refused by the check
Cache:           unchanged keys per alias; entries expire with their TTL
Safety:          the free tier: only authored inputs reach this key
Contract:        no shape moves; configuration refuses text-long (changelog CHANGE)
Invariants:      ARCH-005 §2 (ids only in the register, now pinned and stable), INV-017 (no threshold moved)
Blast radius:    SYSTEM — the model behind every text capability
Decision level:  3
ADR:             none (ADR-004 holds; D-043, D-044)
```

## The probe, measured not anecdotal
One-line calls ("Reply with the single word: ok", 8 output tokens), no corpus text:
```
round  time (UTC)   3.1-flash-lite  3.5-flash-lite  3.5-flash  3.6-flash  3.7-flash  3.8-flash  3.1-pro-preview
1      15:19        503             timeout         200        200        503        503        429
2      15:30        503             503             timeout    200        503        503        429
3      15:41        503             timeout         timeout    timeout    503        503        429
4      15:52        503             timeout         200        200        503        503        429
5      16:04        503             503             timeout    200        503        503        429
6      16:28        503             timeout         timeout    200        503        503        429
7      16:35        503             503             503        200        503        503        429
8      16:40        503             503             503        200        503        503        429
```
Rounds 1–5 shared the line with a pipeline's package downloads; rounds 6–8 did not. Every `503`
said "high demand"; every `429` said the quota is exhausted (the preview has no free tier).

## The choices
- **`text-default` → `gemini-3.6-flash`.** Stable on the provider's model page ("Stable:
  `gemini-3.6-flash`", updated July 2026), 1 048 576 in / 65 536 out (read twice), 7 of 8 probes.
- **`text-fast` → the same row.** Both stable lite models answered nothing in 16 calls. The alias
  stays, so an environment moves to a cheaper row the day one answers, with no configuration change.
- **`text-long` unavailable.** The only long-context model is `gemini-3.1-pro-preview`. A preview
  can change or vanish under a recorded fixture, which the register promises never happens. No
  capability uses `text-long` today. The vocabulary keeps the word; `contract/models.UNAVAILABLE`
  names the reason; the settings refuse it at load.
- **`embed-default` unchanged.** `gemini-embedding-001` answers, and every stored vector depends on it.
- **Never** a moving alias or a preview: `tools/checks/models` now refuses `-latest`, `-preview` and
  `-exp` ids inside the register, and any `gemini-…-latest` literal outside it. Both are planted.

## Prices, cited
`https://ai.google.dev/gemini-api/docs/pricing` (updated 2026-09-23), read twice, identical both
times: `gemini-3.6-flash` input $0.75 / output $3.75 per 1M through 2026-12-31, $1.50 / $7.50 from
2027-01-01, output "including thinking tokens". In the register: 750 / 3 750 µ$ per 1k, the
2027 figure in the ledger with its date. The rate-limit page publishes no per-model free-tier
figure; the project's own ceiling for this model is 20 requests a day.

## ARCH-008 §1, priced again
The old row was 300 / 2 500. Today: input × 2.5, output × 1.5. From 2027: × 5, × 3. Each
capability's p95 cost per call was computed from its fixtures' own token counts
(`ceil((input × price_in + output × price_out) / 1000)`, the 95th percentile over the set). The
method reproduces the eval harness exactly on the old price (its column equals the recorded run):
```
set                 budget   2.5 (eval)   3.6 today   3.6 from 2027
documents-generate    8000       1234        2057          4113
documents             8000        339         654          1307
generate-children     6000       1395        2182          4364
generate-tests        8000       2612        4120          8240   over by 240 (3 %)
improve-story         2000        448         748          1496
post-mortem           8000       1716        2733          5465
propose-workflow      6000       1432        2208          4415
release-notes         6000       1772        2893          5786
summarize             4000       1002        1717          3434
unfurl                1000        183         293           585
assistant             6000        211    (bound ×5: 1055)    holds
translate             2000         48         419   (the fast row moved from lite to flash)
```
Every descriptor holds today. `generate-tests` does not hold at the 2027 price: no budget is widened
now (`D-043`); the recorded fixtures measure it before that price applies. The authored fixtures
carry no thinking tokens, and the rows send `minimal`, so thinking adds nothing here.

## Red first
```
tests/unit/providers/gemini/test_models.py        ImportError: cannot import name 'UNAVAILABLE'
tests/unit/tools/test_authored_dispatch.py        an improve-story request got {'facts', 'rationale', 'summary'}
tools/checks/models on its plants                 (before) 1 violation; (after) 4 — the named ids and both register rows
```

## A stand-in collision the re-generation found (`F-041`)
Re-generating `improve-story` gave every case an unfurl card, and its set went to 0.000. The
stand-in picks a builder by the first segment marker it finds; `unfurl`, added after
`improve-story` was last authored, claimed `<<<title>>>`, which `improve-story` also sends. Its
`<<<description>>>` would have matched the workflow builder next. `improve-story` is now dispatched
on `<<<focus_hint>>>`, after `generate-children`, which also sends it. Every text set was then
re-generated again (977 fixtures, the same count per set as before) and every set run.

## Every set, re-run on the moved rows (authored fixtures, re-generated)
```
assistant 1.000 · documents 1.000 · documents-generate 1.000 · documents-ingest 1.000 ·
generate-children 1.000 · generate-tests 1.000 · improve-story 1.000 · post-mortem 1.000 ·
propose-workflow 1.000 · release-notes 1.000 · search 0.950 · summarize 1.000 · translate 1.000 ·
unfurl 1.000 — EVALS GREEN; every p95 cost as in the table above, every latency far under budget
```
The grader question, stated plainly: the 2.5 grader refuses this key, so "new model, same grader"
cannot be run against a model grader. It does not need to be: no set grades with a model today
(every grader is code). The numbers measure the pipeline, the scanners, the graders and the new
price against the authored stand-in, never the new model's judgement.

## The grader, moved last (`D-044`)
`grader-default` moves to `gemini-3.6-flash` in its own change. Every set was re-run after it and
the numbers are identical, as they must be when nothing grades with a model; they are stated as
re-baselined, not compared with the 2.5 numbers. `git diff` of every `thresholds.yaml` except the
search latency tightened in session 021: empty.

## The free tier, stated
This key is on the free tier: the provider may use prompts and completions to improve its
products. `RETENTION` and the providers ledger now say so instead of the paid-tier line they
carried. Only authored inputs have reached the key. The live calls this ticket made: 35 + 21
probe calls and 3 thinking calls, all one-liners.

## Verify
On the final tree (every change above, the stand-in and the timestamp fixes included):
```
$ make verify
GATE GREEN (49 checks)
oasdiff: no breaking change against main
TOTAL                                                            6802     25    842     21    99%
863 passed in 142.09s (0:02:22)
   recall_at_10           0.914  (floor 0.85)
   mrr                    0.787  (floor 0.7)
   tenant_isolation       1.000  (floor 1.0)
EVALS GREEN
No known vulnerabilities found
INF no leaks found
selftest: 51/51 checks red on their plant
VERIFY GREEN
exit=0 elapsed=387s
```
```
$ make ci
GATE GREEN (49 checks)
oasdiff: no breaking change against main
TOTAL                                                            6802     25    842     21    99%
863 passed in 301.03s (0:05:01)
   recall_at_10           0.914  (floor 0.85)
   mrr                    0.787  (floor 0.7)
   tenant_isolation       1.000  (floor 1.0)
EVALS GREEN
No known vulnerabilities found
INF no leaks found
selftest: 51/51 checks red on their plant
VERIFY GREEN
stamp: tree db98fd42212b in python:3.12.14-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9 at 2026-09-23T21:08:11+00:00 -- green
exit=0 elapsed=1785s
```
One `make ci` run on this same tree went red before the one above: `test_round_trip_through_the_child`
ran past its 15 s deadline parsing two lines of Markdown in the child. Its test phase took 455 s
against the usual 205 s, with another repository's pipeline container on the same Docker at the
time. The deadline is a safety bound and was not loosened; the re-run, unchanged, is above. The
push re-runs the pipeline once more, because this record changed after the stamp.

## A test that depended on the second it ran in (`F-042`)
The `make ci` run after the record was pasted went red on a test outside this ticket:
```
FAILED tests/unit/tools/test_install.py::test_a_verified_archive_is_downloaded_once_and_a_corrupted_cache_is_fetched_again
RuntimeError: gitleaks_8.30.1_linux_x64.tar.gz: sha256 577f4fad… does not match the pinned 882425f0…; refused
1 failed, 861 passed
```
No download happened (`urlopen` is the test's fake; "downloading" is a print). Both digests are
the test's own fake archive, built twice: once for the pin, once to serve. It was gzip-compressed
with the current time in its header, so two builds in different seconds differ. A test that moves
the clock between two builds was red first (`At index 4 diff`, the gzip timestamp); the archive is
now compressed with `mtime=0`. Both gates were run again on the tree with the fix (above).

## Decisions and questions
- `D-043` (the rows move; `text-long` unavailable; budgets held, 2027 overrun re-measured later), `D-044` (the grader moves on its own).
- `F-034` closed; `F-041` and `F-042` found and closed.

## Commit
1. `fix(tools): the stand-in answers improve-story as improve-story` — tools/authored.py, tests/unit/tools/test_authored_dispatch.py
2. `feat(providers): the text rows move to a stable 3.x model; text-long unavailable` — src/catalyst_ai/contract/models.py, src/catalyst_ai/config/settings.py, src/catalyst_ai/providers/gemini/models.py, tests/unit/providers/gemini/test_models.py, tests/unit/providers/gemini/test_aliases.py, tests/unit/providers/gemini/test_adapter.py, tools/rules.py, tools/checks/models.py, tools/checks/selftest/plants/models/**, docs/01-architecture/ARCH-008-cost-and-budgets.md, docs/04-ledgers/contracts-changelog.md, .env.example, brain/01-STATUS.md, brain/02-DECISIONS.md, brain/03-FINDINGS.md, this record
3. `gen(fixtures): authored fixtures and ledgers for the moved text rows` — tests/fixtures/providers/gemini/** (twelve text sets), docs/04-ledgers/{providers,config,capabilities,eval-sets}.md
4. `feat(providers): the grader moves to the text row, on its own` — src/catalyst_ai/providers/gemini/models.py, tests/unit/providers/gemini/test_models.py, brain/02-DECISIONS.md
5. `gen(ledgers): the grader's register row` — docs/04-ledgers/providers.md
6. `test(tools): the fake release archive is the same bytes in any second` — tests/unit/tools/test_install.py (committed first, before 1)
Green light: yes, given in this session, for all six on a green `make ci`

## Next
The extended nightly, then the change-aware gate. The live recording (AI-013) is parked.
