# 062 — The commit-time gate reads the staged files, under ten seconds

**Date:** 2026-10-10 · **Ticket:** AI-049 · **Capability or package:** `tools/checks/gate.py`, `tools/checks/vocabulary.py`, `tools/precommit.py`, RULE-005, RULE-006, `D-070` · **Author:** a contributor

Commit and push are held to thirty seconds together. The previous commit measured 40 s, and
`gate --fast --staged` alone took 17.7 s. Timed per check with a one-file scope: the deployment
check 5.0 s (it imports the settings), the text scan 4.0 s and naming 2.8 s (the scoped walk still
visited and resolved every file of the tree), dupl 1.5 s, structure 1.1 s.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-049
Capability:      none — the commit-time gate
Inputs:          the staged set
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged
Budget:          unchanged
Failure mode:    a cross-file finding in a file the commit did not touch waits for the hosted run
Cache:           none
Safety:          unchanged; gitleaks still reads the staged tree and the pushed range
Contract:        unchanged
Invariants:      unchanged
Blast radius:    LOCAL — the commit-time gate
Decision level:  2 — D-070 (the lead)
ADR:             none
```

## Changed
- `gate.walk` and the text scan iterate the staged set when a scope is set, instead of the tree.
- `gate.main --staged` gives the per-file checks the staged files even when the ground moves;
  `CROSS_FILE_READS` names what `dupl`, `structure` and `deployment` read, and each runs only
  when a staged file is under it (all of them when the ground moves).
- RULE-005 §1, RULE-006 §2 and the precommit docstring say so; `D-070`.

## Tests run
- `pytest tests/unit/tools` — 176 passed (two new: the cross-file selection; the text scan reads
  the scope and not the tree)
- `mypy` on the three changed files — clean
- timed `gate.main(["--fast", "--staged"])`: a page 0.5 s, `app.py` 3.2 s, `config/settings.py`
  4.3 s, `tools/checks/gate.py` (the ground) 8.2 s — before: 17.7 s scoped, about 40 s full

## Eval and budget numbers
No capability touched.

## Decisions and questions
- D-070 filed.

## Commit
Line: `perf(gate): the commit-time gate reads the staged files, under ten seconds`

## Next
The commit and push time ship prints on this commit.
