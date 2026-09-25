# 052 — The kill switches are spelt the way the settings read them

**Date:** 2026-09-25 · **Ticket:** AI-040 (1 of 2, F-047) · **Capability or package:** the fourteen capability descriptors, `tools/checks/capabilities.py`, `.env.example`, `ARCH-005`, `RULE-009`, the config ledger, the kill-switch and staging runbooks, the glossary · **Author:** a contributor

`F-047`: every descriptor, the capabilities check and every document named a capability's switch
`CATALYST_AI_CAPABILITY_<NAME>_ENABLED`. The settings nest with two underscores
(`env_nested_delimiter="__"`), so the variable they read is `CATALYST_AI_CAPABILITY_<NAME>__ENABLED`.
The documented spelling was an unknown variable, and unknown variables are ignored: an operator
following the kill-switch runbook would have set it, seen no error, and left the capability on.

## Read
- `config/settings.py`: `env_prefix="CATALYST_AI_"`, `env_nested_delimiter="__"`, the per-capability
  settings a nested model under `capability_<name>`.
- Checked by running, not by reading: `CATALYST_AI_CAPABILITY_SUMMARIZE_ENABLED=false` left
  `settings.capability_summarize.enabled` true; `…SUMMARIZE__ENABLED=false` turned it off.
- D-040 and the contracts changelog record what was decided and published at the time; they are
  history and keep their text.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-040 (F-047)
Capability:      all fourteen — the kill switch's name only
Inputs:          none
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged
Budget:          unchanged
Failure mode:    fixed: the documented switch now does what it says
Cache:           none
Safety:          the kill switch works as the runbook says
Contract:        unchanged (the switch is an operator's variable, not the API)
Invariants:      unchanged
Blast radius:    CAPABILITY — the fourteen descriptors (the switch name only), one check, documents
Decision level:  1
ADR:             none
```

## What changed
- **The descriptors**: each `kill_switch` names `CATALYST_AI_CAPABILITY_<NAME>__ENABLED`.
- **The capabilities check** expects that spelling, so a descriptor with the old one is refused.
- **`.env.example`, `ARCH-005`, `RULE-009`, the config ledger, the kill-switch and staging runbooks,
  the glossary** spell the nested settings with `__` (`…__ENABLED`, `…__MODEL_ALIAS`).
- **The test that proves the name works** (`tests/unit/config/test_kill_switch_names.py`: every
  descriptor's switch is a declared variable, and summarize's, set to `false`, turns summarize
  off) lands with the next change (053), because it reads the settings through the environment
  that change gives `load_settings`.

## Red first
```
the summarize descriptor given the old spelling back
  capabilities check: kill_switch must be CATALYST_AI_CAPABILITY_SUMMARIZE__ENABLED   GATE RED
  (with 053's test in the tree: test_each_descriptors_kill_switch_is_a_name_the_settings_read
  FAILED too)
restored: green
```

## Eval and budget numbers
No capability's behaviour changed; no eval set moved.

## Verify
Fast checks: `make verify-fast` — `GATE GREEN (17 checks)`, `EVALS GREEN`,
`VERIFY-FAST GREEN`. The full gate runs before this is pushed; its output is pasted here then.

The full gate on the tree this change is committed from:
```
$ make verify
VERIFY GREEN — GATE GREEN (56 checks) · 1189 passed, coverage 99.41% · EVALS GREEN · selftest 58/58 (on the host, before record 043's make hooks fix)
$ make ci
VERIFY GREEN in catalyst-ai-ci:d06a9811d6b3 — 56 checks · 1189 passed, 99.41% · EVALS GREEN · selftest 58/58 · stamp: tree f777f5806cb3 at 2026-09-25T07:16:19+00:00 -- green
```

## Decisions and questions
- `F-047` closed by this change and the next (053), which makes a misspelling refuse the start.

## Commit
- `fix(capabilities): name each kill switch the way the settings read it`
