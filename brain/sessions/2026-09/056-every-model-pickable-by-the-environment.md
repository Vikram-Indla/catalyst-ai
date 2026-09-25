# 056 — Every model pickable by the environment, among the rows the register prices

**Date:** 2026-09-25 · **Ticket:** AI-044 · **Capability or package:** `config/pins.py` (new), `config/settings.py`, `providers/gemini/aliases.py` (`check_pins`, the pins in `resolve`), `providers/gemini/models.py` (`TEXT_IDS`, `EMBEDDING_IDS`), `providers/gemini/adapter.py`, `cli.py`, `tools/checks/config.py`, `.env.example`, the config and providers ledgers, `D-064` · **Author:** a contributor

The lead asked that every model be swappable without code: one environment variable per alias,
with a default in code, checked at start, and a bad value refusing the start by name. Gemini is the
only provider, and the service already has no other. The repository's law narrows one point:
a model the register does not price has no price to charge the budget against, and no eval set
has measured it (`ARCH-008 §1`, `D-043`). So a pin may name any of the register's priced ids for
its alias's class, and nothing else. That narrowing is `D-064`, which the lead kept.

## Read
- The register (`providers/gemini/models.py`) prices one text id and one embedding id; every text
  alias resolves to the text row.
- `tools/checks/models` (an architecture test): a model id may appear only in an adapter's
  `models.py`. So the list of ids a pin may name is derived in the register, never written in
  configuration or a leaf.
- Configuration sits below the providers in the import layers, so configuration cannot check an
  id against the register. The provider checks it when it is built, before the process serves,
  and `catalyst-ai check` checks it too.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-044
Capability:      none — every capability's model resolution
Inputs:          four optional environment variables (model ids, PUBLIC)
Tenant boundary: unchanged
Provider/model:  unchanged by default; a pin names only a priced register row
Prompt version:  unchanged
Eval set:        unchanged
Budget:          unchanged (a pinned row carries its own price)
Failure mode:    new start refusal: an unpriced pin, named
Cache:           unchanged (keys carry the concrete model id)
Safety:          no other provider or endpoint can be named; a pin cannot reach an unmeasured
                 model, and cannot route around residency (INV-072)
Contract:        unchanged
Invariants:      unchanged
Blast radius:    PLATFORM — configuration and the provider's resolution
Decision level:  2 — D-064 (the lead)
ADR:             none
```

## What changed
- **`config/pins.py`**: `MODEL_TEXT_DEFAULT`, `MODEL_TEXT_FAST`, `MODEL_GRADER_DEFAULT`,
  `MODEL_EMBED_DEFAULT`, each optional (unset keeps the register's row). `Settings` inherits them,
  so each is a top-level variable and the unknown-variable refusal knows them.
- **The register** derives `TEXT_IDS` and `EMBEDDING_IDS` from its rows.
- **`aliases.check_pins`** refuses a pin outside its class's priced ids:
  `CATALYST_AI_MODEL_TEXT_FAST: '…' is not a priced model for text-fast; the register prices […]`.
  The provider calls it when it is built. `catalyst-ai check` and every command that loads the
  settings print the refusal and exit 1.
- **`aliases.resolve`** returns the pinned row when a pin is set, the register's row otherwise.
  This applies after the environment's alias selection, so `MODEL_TEXT_ALIAS=text-fast` then uses
  `text-fast`'s pin.
- **Residency is untouched (`INV-072`).** A pin changes the model id in the request path, never
  the endpoint: every call still goes to the regional endpoint of the configured in-Kingdom
  location (`_url` builds it from the location, not from the model). And a pin can only name a
  register row, and every row is served there (each still marked unverified in-region until the
  account's model list).
- **The config check** (`tools/checks/config`, full gate only) read the settings by parsing the
  `Settings` class alone, so the four inherited pins looked like ledger rows without a setting.
  It now follows `Settings`' bases that the config package defines.
- **`.env.example`**, the **config ledger** (four rows) and the **providers ledger** (a paragraph)
  document the variables. The embedding pin notes that a change means `catalyst-ai reembed`.

## Red first
```
the pin check in the leaf, first cut
  tests/architecture: test_no_model_id_outside_register   FAILED (ids written in contract/models.py)
  → moved to the register; configuration carries only the choice
check_pins made a no-op
  test_an_id_the_register_does_not_price_refuses_the_start_by_name   5 FAILED
  test_check_and_serve_refuse_an_unpriced_pin_naming_the_variable    FAILED
restored: 13 passed; providers + config + architecture 165 passed; the fast gate green
settings.py at 317 logical lines (budget 300) → the pins moved to config/pins.py
make verify: GATE RED at config — MODEL_TEXT_DEFAULT … is a ledger row without a setting (4)
  (the check parsed Settings alone); the bases followed → config green
  test_a_setting_inherited_from_a_config_base_is_a_setting: bases ignored → 2 FAILED; restored 2 passed
```

## Eval and budget numbers
No capability changed; no eval set moved. Nothing heavy ran: the machine is shared tonight, and the
full gate runs before this is pushed.

## Verify
Fast checks: lint, types, the import contracts (5 kept), the tests above, the static gate green
(17 checks). The full gate, on the tree this change is committed from:
```
$ make verify
VERIFY GREEN — GATE GREEN (56 checks) · 1217 passed, coverage 99.42% · EVALS GREEN · selftest 58/58 (on the host, on the final tree)
$ make ci
VERIFY GREEN in catalyst-ai-ci:d06a9811d6b3 — 56 checks · 1217 passed, 99.42% · EVALS GREEN · selftest 58/58 · stamp: tree 853cbf005fc8 at 2026-09-25T11:40:25+00:00 -- green
```

## Decisions and questions
- `D-064` (the lead): pins only among priced rows. **Today each class has one row, so a pin can
  only restate it.** Swapping for real needs a second row per class: its published price, read
  twice, and an eval run. That is a small change the lead can ask for by naming the model.
- The alternative, any Gemini id accepted, is not built. It would need a price source outside the
  register, and a swap that no eval has measured.

## Commit
- `feat(config): each model alias pickable by the environment, among priced rows`
- `gen: the config ledger names the four model pins`
