# 060 — A development-only stand-in for the model, so the local walk works end to end

**Date:** 2026-09-25 · **Ticket:** AI-047 · **Capability or package:** `providers/standin.py` (new), `config/standin.py` (new), `config/settings.py`, `config/deployed.py`, `app.py`, `.importlinter`, `.env.example`, the config ledger, `D-068` · **Author:** a contributor

The lead's local walk of the product needs the record's Improve menu and the command centre's
briefing to work end to end, with no model available on the workstation. This adds a stand-in provider for development only. It answers
model calls with fixed text that says it is a stand-in, and the capabilities' own rules judge that
text as they judge a model's. So the walk shows the real behaviour, including a refusal. The
settings refuse it outside development.

## Read
- The provider port (`providers/port.py`): `generate`, `stream`, `embed`, `count_tokens`,
  `model_id`, `credentials_ready`. A provider sees the capability's name and the prompt's
  segments; each user field is fenced (`<<<name>>>` … `<<<end name>>>`).
- The Improve menu's operations and their model output shapes:
  - `improve-story`: `description`, `acceptance_criteria`, `rationale`, `changed`;
  - `generate-children`: `candidates[] {type, title, description, acceptance_criteria}`,
    `empty_reason`, `rationale`;
  - `summarize`: `summary`, `participants_mentioned`, `empty_reason`, `rationale`.
- The governed-record rule refuses a number the member's hint names but no source carries
  (`fact_added`); draft-only children withhold a candidate carrying a figure. The stand-in uses
  both, so a refusal can be shown without faking one.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-047
Capability:      none changed — a development-only provider behind the port
Inputs:          one setting, PROVIDER_STAND_IN (development only)
Tenant boundary: unchanged
Provider/model:  unchanged by default; on, no model is called and nothing leaves the machine
Prompt version:  unchanged
Eval set:        unchanged (evals run on recorded fixtures, never the stand-in)
Budget:          the stand-in costs nothing (cost 0 per call)
Failure mode:    any operation outside the Improve menu answers ai.provider.unavailable
Cache:           unchanged; responses name the stand-in as their model
Safety:          refused outside development; every answer is marked as a stand-in
Contract:        unchanged
Invariants:      unchanged
Blast radius:    PLATFORM — the composition root and the configuration
Decision level:  2 — D-068 (the lead)
ADR:             none
```

## What changed
- **`providers/standin.py`** answers:
  - `improve-story`: the text as written, marked "Stand-in suggestion, no model:", so every fact
    survives. A text that opens with a markdown heading (a charter's `## Hypothesis` …) keeps the
    heading first and the mark inside that section, so the sections split back as they were sent. When the member's focus hint names a number, the stand-in writes it in, and the
    governed rule refuses it: the withheld state.
  - `generate-children`: two marked drafts at the child level, and a third carrying a figure,
    which draft-only mode withholds and counts.
  - `summarize`: one marked line, naming nobody.
  - `brief`: three marked summary sentences, a highlight and a risk, each citing the chain's own
    ids (read from the fenced chain, `theme [id]`, `objective [id]` …), with no number at all, and
    one `unsupported` line ("not stated in the data"). The brief's rule refuses a citation outside
    the chain, so a wrong id could never slip through. A refusal here would blank the whole panel,
    so the walk's limit case is the unsupported line.
  - Embeddings are deterministic unit vectors of the index's dimension, drawn from each text's
    hash, so indexing and similar-item search run, with no meaning.
  - Similar-item search needs no answer: it runs on the vectors.
  - Any other operation answers `ai.provider.unavailable`; streaming answers an error frame. The
    stand-in needs no credential, and every call costs nothing.
- **`config/standin.py`**: `PROVIDER_STAND_IN`, false by default, inherited by `Settings`.
  **`config/deployed.py`** refuses it outside development.
- **`app.py`** builds the stand-in instead of the regional provider when the switch is on.
- **`.importlinter`** puts the stand-in beside the other adapters.
- **`.env.example`** carries the commented switch and what it shows, and says that the example's
  signing pair is the tests' fixed seed, to be replaced by your own for a local run. The config
  ledger has its row.

## Red first
```
the refusal outside development removed
  test_the_stand_in_is_refused_outside_development   FAILED
the figure from the member's hint not written in
  test_a_hint_that_names_a_number_shows_the_withheld_refusal   FAILED
the mark put before a charter's first heading
  test_a_charter_keeps_its_sections_with_the_mark_inside_the_first   FAILED
a briefing citing an id the chain does not carry
  test_the_briefing_cites_only_the_chains_ids_and_says_what_it_cannot_support   FAILED (untraceable_entry)
restored: test_standin (providers) 8 passed; providers, config, brief and architecture 192 passed;
  earlier: test_standin (config) 2 passed; config, providers,
  tools, architecture and health 355 passed; the static gate green once this record claims its radius
```

## Eval and budget numbers
No capability changed; no eval set moved.

## Verify
Fast checks: lint, types, the import contracts (5 kept), the tests above. The full gate, on the
tree this change is committed from:
```
$ make verify
(pending: pasted from the run)
$ make ci
(pending: pasted from the run)
```

## Decisions and questions
- `D-068`, decided by the lead.

## Commit
- `feat(providers): a development-only stand-in for the local walk`
- `gen: the config ledger names the stand-in switch`
