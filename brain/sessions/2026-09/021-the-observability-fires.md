# 021 — the observability fires

**Date:** 2026-09-23 · **Ticket:** AI-018 · **Capability or package:** platform/observability, platform/pipeline (the door), tools/checks (alerts, latency), ops/alerts.yaml, the runbooks, `search` (descriptor and set threshold) · **Author:** a contributor

A review of the alerts found six ways they would fail at night. Session 018 changed code for all
six, but not every change had a test that could fail, and two were only half done. This session
proves each one red on the tree before session 018 (`c93f07d`) or on today's tree, then green.

## Read
`ARCH-008 §1`, `ARCH-010 §2 and §5`, `RULE-006`; `cli.py`, `app.py`, `platform/observability/**`,
`platform/pipeline/door.py`, `ops/alerts.yaml`, every runbook, every descriptor's budget; the
review's six findings and session 018's record.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-018
Capability:      none added; `search` descriptor p95_latency_ms 2 000 → 800 (ARCH-008 §1)
Inputs:          none
Tenant boundary: the organisation id as a metric label on one new counter (budget refusals), the class
                 the cost series already carries (slos.md, "what is deliberately not measured")
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        search v1 threshold p95_latency_ms 2000 → 800 (tighter; measured 40 ms)
Budget:          search tightened to the architecture's figure; every other budget unchanged
Failure mode:    an alert that cannot fire, that fires at another capability's number, that cannot
                 name its tenant, that points at another page, or that reads a stale gauge
Cache:           none
Safety:          no content in any label (ARCH-010 §1); the organisation id only, never a name
Contract:        no shape moves; the search budget is a changelog FIX
Invariants:      INV-064, INV-065, INV-066 (new)
Blast radius:    PLATFORM — every alert, one counter, one descriptor
Decision level:  2
ADR:             none
```

## Red first: findings 1, 2 and 6 on the tree before the fix
A script wired the pre-fix tree the way its `cli.py` did (`ops = create_app(...)`,
`SecurityCounters()`), then ran against `c93f07d`'s sources:
```
finding 1: worker quarantined 1 row; process registry holds 0; scrape status 401 -> RED
finding 2: 1 scrape + 2 probes on the ops port counted as 3.0 service requests -> RED
finding 6: depth 57 read, then the store went down; gauge still renders 57.0 -> RED
```
**Finding 1.** The fix already existed, but its test built its own `Worker` and passed the
registry by hand, so it tested a copy of the wiring and not the wiring. `cli.assemble_worker`
now builds the worker and its ops port together, on the ops port's registry. The command and the
contract test both call it, and the test reads the quarantine back from the scrape.
**Finding 2.** Covered by session 018's ops-app tests (a probe and a scrape leave the request
total at 0). No change here.
**Finding 6.** Session 018's test began with an empty registry, so it also passed on the old code
(`F-037`). A new test reads a depth of 1, fails the read, and asserts the series is gone. It was
run against `c93f07d`:
```
FAILED tests/unit/platform/observability/test_scrape_new.py::test_a_depth_read_before_an_outage_does_not_survive_the_failed_read
```

## Finding 3 — one number for many budgets
Session 018 gave retrieval its own rule, but everything else was still judged at 8 s. The
descriptors declare seven different budgets. **Red:** a new check, `tools/checks/latency`, holds each
served operation (from the document's `x-capability`) and each capability to its descriptor's
`p95_latency_ms`. Run against today's alerts:
```
operation improve_story.run fires above 8.0 s; budget 4000 ms
operation translate.run fires above 8.0 s; budget 6000 ms
operation documents.ask fires above 8.0 s; budget 15000 ms
operation search.run fires above 0.8 s; budget 2000 ms
capability improve-story fires above 8.0 s; budget 4000 ms
… 25 violations: 15 of 20 judged operations, 10 of 12 capabilities
```
The `search` line exposed `F-036`: the descriptor had widened `ARCH-008 §1`'s 800 ms to 2 000
with no decision. It is tightened back in the descriptor and in the set's threshold (the set
measures 40 ms). **Fix:** one `CapabilityLatencyHigh` rule per budget (4, 6, 8, 10, 12, 15 s),
`RetrievalLatencyHigh` at 0.8 s for search and the index operations, and one
`ProviderLatencyHigh` per budget as well, since it had the same single 8 s. `BUCKETS_S` gains
edges at 4, 6, 12 and 15 s. The check also refuses an operation judged by no rule or by two, and
a threshold that is not a bucket edge. It is green on the tree and red on its plant. The card's
own line is a test: a 1 s `search.run` breaches (0.8 s), and a 1 s `generate_children.run` does
not (8 s).

## Finding 4 — the budget alert could not name the tenant
Session 018 made the summary point at a query. `ARCH-008` promises budget refusals per
organisation, so the alert now names the tenant itself. **Red:** a door test asserting
`catalyst_ai_budget_refused_total{capability="x",organization="<id>"} 1` after a refusal failed
against an empty render. **Fix:** the door counts a cap refusal under the organisation and the
capability. `TenantBudgetExhausted` groups by both, and its summary names them.
**Cardinality, decided:** the organisation label was already carried on the cost series. A
refusal series exists only for an organisation that reached its cap, so it never outgrows the
cost series. The error counter stays on `code` alone. `slos.md` says so, and the runbook's first
command is the new series.

## Finding 5 — runbooks about something else
**Red:** `tools/checks/alerts` now requires every alert's runbook to carry a heading that names the
alert. Run against `c93f07d`'s alerts and runbooks, it names the review's cases and one the review
missed:
```
docs/06-runbooks/key-rotation.md: OriginForged points here; no heading names it
docs/06-runbooks/job-quarantine.md: OriginRefusalsHigh points here; no heading names it
docs/06-runbooks/retention.md: OriginUnverifiable points here; no heading names it
docs/06-runbooks/index-rebuild.md: IndexUnavailable points here; no heading names it
… 13 violations
```
On today's tree, `IndexUnavailable` still pointed at the re-embedding page. **Fix:**
`index-unavailable.md` (what stops, what keeps answering, the three commands, why a rebuild
never helps). Each page's title or a section names its alert. `capabilities.md` gains sections
for the burn, latency and cache alerts, and `provider-outage.md` one for provider latency.
`job-quarantine.md` is about `JobQuarantined` alone, and hands the door's refusals to
`origin-refusals.md`. The check is red on its plant, and `RULE-006` has both rows (the stray
cell in the alerts row is gone).

## The gate's own threshold check read budgets upside down
Tightening `search` turned the gate red: `threshold p95_latency_ms lowered without a D-NNN`. The
check treated every key as a floor. On the old helper:
```
ceiling raised 800->2000, today: []
ceiling tightened 2000->800, today: ['p95_latency_ms']
```
So a budget could be widened in a set with no decision, which `RULE-000` forbids, and a
tightening was refused (`F-038`). `evals.loosened` now reads the two ceilings the other way. Four
tests cover it; two were red on the old helper. `RULE-006`'s eval row says it.

## Verify
```
$ make verify
GATE GREEN (49 checks)
oasdiff: no breaking change against main
TOTAL                                                            6789     25    838     21    99%
853 passed in 201.41s (0:03:21)
   recall_at_10           0.914  (floor 0.85)
   mrr                    0.787  (floor 0.7)
   tenant_isolation       1.000  (floor 1.0)
   p95 latency 35 ms (budget 800.0)                      (search)
EVALS GREEN
No known vulnerabilities found
INF no leaks found
selftest: 51/51 checks red on their plant
VERIFY GREEN
exit=0 elapsed=548s
(on the host; the storage tests and the evals through a throwaway container of the pinned image)
```
```
$ make ci
uv run --frozen python -m tools.stamp begin
ci-postgres: catalyst-ai-ci-postgres healthy on catalyst-ai-ci as postgres
GATE GREEN (49 checks)
oasdiff: no breaking change against main
TOTAL                                                            6789     25    838     21    99%
853 passed in 297.80s (0:04:57)
   recall_at_10           0.914  (floor 0.85)
   mrr                    0.787  (floor 0.7)
   tenant_isolation       1.000  (floor 1.0)
EVALS GREEN
No known vulnerabilities found
INF no leaks found
selftest: 51/51 checks red on their plant
VERIFY GREEN
stamp: tree 2e15539f3470 in python:3.12.14-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9 at 2026-09-23T15:40:31+00:00 -- green
exit=0 elapsed=1413s
(an earlier attempt was killed with its shell mid-run and its database removed; this run began from a clean
network; nothing named catalyst-ai-ci left in `docker ps -a` afterwards)
```

## Eval and budget numbers
Only `search`'s budget moved. It is tighter, and the set measures 40 ms against 800. No prompt,
model or grader changed.

## Decisions and questions
- `D-042` proposed (alerts held to what they are about, by the gate; the refusal counter; search at 800 ms).
- `F-036` (search widened its budget without a decision), `F-037` (a test that could not fail; a link to the wrong page), `F-038` (the threshold check read budgets upside down) — all closed here.
- `INV-064`, `INV-065`, `INV-066` added.

## Commit
1. `fix(observability): alerts at each declared budget, naming tenant and runbook` (the approved line, cut to 80 characters by the commit-msg hook) — src/catalyst_ai/cli.py, src/catalyst_ai/platform/observability/metrics.py, src/catalyst_ai/platform/pipeline/door.py, src/catalyst_ai/capabilities/search/descriptor.py, evals/search/thresholds.yaml, tools/checks/latency.py, tools/checks/alerts.py, tools/checks/evals.py, tools/checks/gate.py, tools/checks/selftest/__init__.py, ops/alerts.yaml, tests/contract/test_jobs.py, tests/unit/platform/pipeline/test_door.py, tests/unit/platform/observability/test_scrape.py, tests/unit/tools/test_latency.py, tests/unit/tools/test_alerts.py, tests/unit/tools/test_eval_thresholds.py
2. `docs(runbooks): a heading per alert, and a page for the unreachable index` — docs/06-runbooks/*.md, docs/04-ledgers/{slos,invariants,contracts-changelog}.md, docs/02-rules/RULE-006-enforcement.md, brain/{01-STATUS,02-DECISIONS,03-FINDINGS}.md, this record
Green light: yes, given in this session after the gates were running, for both commits once `make ci` is green

## Next
The model migration (AI-019); its availability probe is already running.
