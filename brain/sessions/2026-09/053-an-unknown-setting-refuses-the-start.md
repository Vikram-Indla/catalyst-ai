# 053 — An unknown setting refuses the start

**Date:** 2026-09-25 · **Ticket:** AI-040 (2 of 2) · **Capability or package:** `config/unknown.py` (new), `config/settings.py` (`load_settings`), `cli.py`, the config ledger, the staging runbook · **Author:** a contributor

The settings ignore a variable they do not declare and keep the default. A misspelt switch —
`CATALYST_AI_CAPABILITIES_ENABLD=false` — would leave every capability on and say nothing; the
wrong nesting (052) did exactly that. Now every variable with the `CATALYST_AI_` prefix must name
a setting, or the process does not start. The refusal names the variables, never their values.
There is no flag that skips it.

## Read
- `pydantic-settings`: unknown variables are ignored for a `BaseSettings` read from the
  environment; `EnvSettingsSource(Settings).env_vars` is the environment as the settings see it
  (case-insensitive, so lower-cased).
- The import contracts: only `config/` reads the environment, and a capability may not reach `os`
  even through an import. So the refusal reads the environment through the settings' own source,
  inside `config/`, and the CLI never touches `os.environ`.
- The tooling's own variables with the prefix, found by search: `RECORD_PROVIDER_TOKEN`
  (`make record LIVE=1`), `EVAL_DATABASE_URL` (the storage tests, the retrieval eval),
  `CI_APT_MIRROR` (`make ci-image`). The service reads none of them.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-040
Capability:      none — the start of every process
Inputs:          the environment's variable names (never their values)
Tenant boundary: unchanged
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged
Budget:          unchanged
Failure mode:    new start-time refusal: an unknown prefixed variable, named
Cache:           none
Safety:          values never printed; the refusal carries names only
Contract:        unchanged
Invariants:      unchanged
Blast radius:    PLATFORM — config (every process starts through it), the CLI
Decision level:  2 (a new start-time rule) — D-062, proposed
ADR:             none
```

## What changed
- **`config/unknown.py`**: `declared()` lists every variable the settings read (each field, each
  nested field with `__`); `unknown()` returns the prefixed variables that are neither settings nor
  in `TOOLING`, sorted; `refuse_unknown()` raises `UnknownSettingsError` naming them:
  `unknown settings: X; no setting has these names (a nested one is spelt with '__':
  CAPABILITY_<NAME>__ENABLED)`. `TOOLING` holds the three tooling variables, each with the command
  that reads it.
- **`load_settings(environ=None)`** refuses before it builds the settings; with no argument it reads
  the environment through `EnvSettingsSource`.
- **The CLI**: `check` and every command that loads the settings print `<command>: <error>` and exit
  non-zero on the refusal.
- **The config ledger and the staging runbook** say what the refusal is and where the allow-list
  lives.
- **`tests/unit/config/test_kill_switch_names.py`**, written for 052, lands here: it reads the
  settings through `load_settings(environ)`.

## The acceptance, point by point
- **Refuses start with a named error, names only.** `serve` with
  `CATALYST_AI_CAPABILITIES_ENABLD=false` prints `serve: unknown settings:
  CATALYST_AI_CAPABILITIES_ENABLD; no setting has these names (…)` and exits 1. The test also plants
  `DISABLED_CAPABILITES`; both names are in the message, neither value is.
- **No skip flag.** None exists; the only extras are the three named in `TOOLING`.
- **Red first with a planted misspelling of the capabilities switch.** Below.
- `.env.example`'s names are all settings or tooling (a test reads it); every descriptor's kill
  switch is a declared name (052's test).

## Red first
```
the refusal removed from load_settings
  test_a_misspelt_capabilities_switch_refuses_the_start_by_name_not_value   FAILED (DID NOT RAISE)
restored: tests/unit/config 63 passed
```

## Eval and budget numbers
No capability changed; no eval set moved.

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
- D-062 (proposed): an unknown prefixed variable refuses the start, in every environment,
  development included; the tooling's variables are an allow-list in code. Record 051's proposal
  had development warn instead; refusing everywhere was asked for, and development is where a
  typo is cheapest to meet.
- A platform that sets a variable with this prefix would have to be added to `TOOLING`; none does
  today (Cloud Run sets `K_*`, `PORT`, `CLOUD_RUN_*`).

## Commit
- `feat(config): a variable no setting names refuses the start, by name only`
