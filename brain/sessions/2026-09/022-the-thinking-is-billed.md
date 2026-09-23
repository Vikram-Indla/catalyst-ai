# 022 — the thinking is billed

**Date:** 2026-09-23 · **Ticket:** AI-019 (first part) · **Capability or package:** providers/gemini (adapter, streaming, models) · **Author:** a contributor

The model migration starts with a defect it would have hidden. The 3.x generation thinks by
default and bills the thinking as output. The adapter counted only the answer, so moving the rows
as they are would have under-counted every call's spend under the tenant cap, the cost metrics and
the budget alerts.

## Read
`ARCH-005 §2`, `ARCH-008 §1–2`; `providers/gemini/{adapter,streaming,models}.py`; the provider's
models, pricing and thinking pages (read 2026-09-23).

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-019 (first part)
Capability:      none; the adapter every capability calls through
Inputs:          none
Tenant boundary: unchanged; the spend the tenant cap counts becomes the billed spend
Provider/model:  register unchanged; a row may now name a thinking level
Prompt version:  unchanged
Eval set:        unchanged (the 2.5 rows send no thinking setting, so every fixture key holds)
Budget:          unchanged
Failure mode:    under-counted spend; an answer cut off after thinking used the output allowance
Cache:           none
Safety:          none
Contract:        Usage.output_tokens counts thinking; changelog FIX, no shape moves
Invariants:      INV-016 (every call carries tokens and cost) and INV-036 (tenant caps) now count what is billed
Blast radius:    PLATFORM — every generation call
Decision level:  2
ADR:             none
```

## Evidence from the provider (one-line calls, the only live calls this part makes)
```
gemini-3.6-flash, "Reply with the single word: ok", maxOutputTokens 64
default                 200  promptTokenCount 7  candidatesTokenCount 1  thoughtsTokenCount 57  total 65
thinkingLevel=minimal   200  promptTokenCount 7  candidatesTokenCount 1  (no thoughts)          total 8
thinkingBudget=0        200  promptTokenCount 7  candidatesTokenCount 1  (no thoughts)          total 8
```
The provider's pricing page says output price includes thinking tokens. With no setting, 57 of the
64-token allowance went to thinking before the one-word answer.

## Red first
```
FAILED tests/unit/providers/gemini/test_adapter.py::test_thinking_tokens_are_billed_as_output          (output 1, expected 58)
FAILED tests/unit/providers/gemini/test_adapter.py::test_a_row_with_a_thinking_level_sends_it_and_a_row_without_sends_none
FAILED tests/unit/providers/gemini/test_streaming.py::test_a_chunk_bills_its_thinking_tokens_as_output (output 4, expected 34)
```

## Changed
- `providers/gemini/models.py` — `billed_output_tokens` (answer plus thinking), the one place both
  paths read usage from; `ModelSpec.thinking_level`, unset on the 2.5 rows.
- `providers/gemini/adapter.py` — `build_body` takes the row and sends `thinkingConfig.thinkingLevel`
  when the row names one; the generate path counts billed output.
- `providers/gemini/streaming.py` — the stream's usage counts billed output.
- tests: three new, one body test given the row.

## Verify
```
$ make verify
GATE GREEN (49 checks)
oasdiff: no breaking change against main
TOTAL                                                            6796     25    840     21    99%
856 passed in 210.20s (0:03:30)
   recall_at_10           0.914  (floor 0.85)
   mrr                    0.787  (floor 0.7)
   tenant_isolation       1.000  (floor 1.0)
EVALS GREEN
No known vulnerabilities found
INF no leaks found
selftest: 51/51 checks red on their plant
VERIFY GREEN
exit=0 elapsed=466s
```
```
$ make ci
GATE GREEN (49 checks)
oasdiff: no breaking change against main
TOTAL                                                            6796     25    840     21    99%
856 passed in 344.27s (0:05:44)
   recall_at_10           0.914  (floor 0.85)
   mrr                    0.787  (floor 0.7)
   tenant_isolation       1.000  (floor 1.0)
EVALS GREEN
No known vulnerabilities found
INF no leaks found
selftest: 51/51 checks red on their plant
VERIFY GREEN
stamp: tree 0d99d2f9eee6 in python:3.12.14-slim@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9 at 2026-09-23T17:33:11+00:00 -- green
exit=0 elapsed=3063s (the package step ran at about 20 kB/s; the gate itself was the usual length)
```

## The push was refused, by a test that waited for time
The pre-push hook re-ran the pipeline (the record changed after the stamp), and it went red:
```
FAILED tests/storage/test_jobs.py::test_the_attackers_rows_inserted_into_the_database_are_quarantined_on_the_real_loop - AssertionError: forged_key
E  assert 'queued' == 'quarantined'
(four `job_quarantined` lines captured: the loop decided four of five rows in its two seconds)
error: failed to push some refs
```
Nothing reached the remote. The test slept a fixed two seconds and then stopped the worker, and a
slow container decides five rows more slowly than that (`F-040`). It now polls until every row has
left `queued` and `running`, bounded at 30 s. Five runs in a row against a real database, all green.
Both gates were run again on the tree with the fix (below).

## Eval and budget numbers
Unchanged: no row thinks yet, so every request, fixture and number is the same.

## Decisions and questions
- `F-039` found and closed; `F-040` (a timing-dependent storage test) found at the push and closed.

## Commit
1. `fix(providers): bill thinking tokens as output; a row names its thinking level` — src/catalyst_ai/providers/gemini/models.py, src/catalyst_ai/providers/gemini/adapter.py, src/catalyst_ai/providers/gemini/streaming.py, tests/unit/providers/gemini/test_adapter.py, tests/unit/providers/gemini/test_streaming.py, docs/04-ledgers/contracts-changelog.md, brain/03-FINDINGS.md, this record
Green light: yes, given in this session, on a green `make ci` (commit 1, made; its push was refused by F-040)
2. `test(storage): wait for the worker to decide every row, not for two seconds` — tests/storage/test_jobs.py, brain/03-FINDINGS.md, this record

## Next
The register rows, once the product owner's question on the fast and long classes is answered.
