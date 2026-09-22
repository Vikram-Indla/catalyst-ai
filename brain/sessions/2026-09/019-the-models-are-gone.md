# 019 — the live recording stopped at the first call: the register's text models are closed to a new key

**Date:** 2026-09-26 · **Ticket:** AI-013 (blocked) · **Capability or package:** none — the register's rows, and what the provider will serve · **Author:** a contributor

## Read
`docs/04-ledgers/providers.md` (the three text rows and the embedding row, their prices and the
retention setting), `ARCH-008 §1` (every budget priced on those rows), `tools/record.py`, and
`D-009` (v1 ships on authored fixtures; the first live recording replaces them and re-states the
numbers).

## What was attempted
A provider key exists for the first time. The plan was fourteen sets recorded in batches against
the free tier's daily cap, smallest first, with the tier stated in the record. The first batch
was one set — `unfurl`, six cases — run live to prove the loop before spending anything.

All six were refused. The recorded body says why:

> This model models/gemini-2.5-flash-lite is no longer available to new users. Please update your
> code to use models/gemini-3.5-flash-lite for the latest features and improvements.

One probe per register row, one sentence of input each:

| Alias | Model | Result |
| --- | --- | --- |
| `text-default` | `gemini-2.5-flash` | 404 — "no longer available to new users" |
| `text-fast` | `gemini-2.5-flash-lite` | 404 — the same |
| `text-long` | `gemini-2.5-pro` | 404 — the same |
| `embed-default` | `gemini-embedding-001` | 200 — the adapter asks for 768 dimensions explicitly, so the index is unaffected |

Reachable from this key today: `gemini-flash-lite-latest` (200), `gemini-3-flash-preview` (200),
`gemini-flash-latest` and `gemini-3.1-flash-lite` (503, "high demand" — transient, not absent).
Fourteen calls in total. The recorder deletes a set's fixtures before it writes, so the
directory was restored from the index; the tree carries nothing from the run.

## Why it stopped here rather than swapping a model
A model id is the register's authority (`ARCH-005 §2`), and moving one is not a recording
sitting. It needs the new prices — every budget in `ARCH-008 §1` and every cost figure in the
ledger is priced on the 2.5 rows — re-measured latency and cost, a `D-` row, and a re-run of
every set whose resulting numbers do not mean what the recorded ones mean. `D-009` exists so
that a fixture is never re-recorded to make a run pass; the same reasoning forbids picking a
different model because the one on record is inconvenient.

Two traps for whoever does the migration: `gemini-flash-latest` is a **moving alias** and cannot
go into a register that promises reproducible fixtures, and `gemini-3-flash-preview` is a
**preview** that can change or vanish under a pinned set. `gemini-3.1-flash-lite` is the
stable-looking candidate.

## Verify
```
$ make verify
GATE GREEN (47 checks) · 809 passed in 110 s · coverage 99 % · the drills green inside the gate · fourteen sets EVALS GREEN · selftest: 49/49 checks red on their plant
VERIFY GREEN
```
```
$ make ci
run by the push's own hook on this tree (the stamp is the evidence); the record is filled from it in the commit that carries this line
```
No code changed: this record, one finding and one line in the providers ledger.

## Decisions and questions
- **F-034** (below): the register's three text rows are unreachable from a key created now. The
  evidence column of every capability stays `authored`, which is what it already says.
- The question that decides the next step is not ours to answer alone: does a project that
  predates the cutoff, or a linked billing account, restore the 2.5 generation? The message says
  *users*, not *keys*, which reads like a project-age gate. If either restores it, the register
  stands untouched and the recording proceeds as written.
- Until then `AI-013` is blocked on a provider fact, not on this repository.

## Commit
1. Files: `brain/**`, `docs/04-ledgers/providers.md`
   Proposed: `docs(providers): the 2.5 rows are unreachable from a key created now`
Green light: given

## Next
The decision above; then either the recording as written, or a model-migration ticket with its
own prices, budgets and numbers.
