# 006 — summaries and translation

**Date:** 2026-09-21 · **Ticket:** AI-006 · **Capability or package:** summarize, translate, evals · **Author:** a contributor

## Read
`ARCH-003`, `ARCH-009 §2–3`, `RULE-004`, `RULE-008`; `improve-story` as the golden shape
(`mode` sections in one prompt file); `Q-001` (a) — people are opaque tokens the backend maps;
`Q-004` — preserve the input's language block by block, no persona, Markdown without fences.
The previous system's `summarize-comments` (a tone per item type, the last 30 comments with
author names from the profiles table, standup status changes grouped in the prompt, 4–8
sentences, both a streaming and a JSON path), `ai-translate-field` and `ai-translate-title`
(Arabic ↔ English with a transliteration rule for technical terms, an exceptions list — keys,
code, links, placeholders, brand names — and Markdown preservation; the target inferred from
the source when absent), and the language-preservation rule of `ai-improve-story` for behaviour.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-006
Capability:      summarize v1.0.0 (modes comments, thread; alias text-default) · translate v1.0.0 (modes field, title; alias text-fast)
Inputs:          summarize: items[].text, item_title · CONFIDENTIAL; items[].id, items[].participant (token p1…p9999), items[].at,
                 item_type, status_changes[] · INTERNAL; mode, target_words, language? · PUBLIC
                 translate: text, context? · CONFIDENTIAL; mode, source_language?, target_language · PUBLIC
Tenant boundary: organization_id on the request; the cache key carries it; no storage rows
Provider/model:  gemini · text-default → gemini-2.5-flash (summarize) · text-fast → gemini-2.5-flash-lite (translate)
Prompt version:  prompt_v1.md for each (system, developer, user fences, mode:* and focus:* sections)
Eval set:        evals/summarize v1 · 106 cases · 10 graders · evals/translate v1 · 94 cases · 8 graders
Budget:          summarize p95 8 000 ms · 4 000 µ$ · timeout 20 000 ms · translate p95 6 000 ms · 2 000 µ$ · timeout 15 000 ms
Failure mode:    as improve-story, plus ai.output.unsafe{participant_not_in_thread} on a summary naming a token outside the
                 thread and ai.input.rejected{target_language_required} on a translation without a target
Cache:           the whole classified request in the key; summarize 900 s, translate 86 400 s
Safety:          the door's scanner over every text; fences around the thread, the status changes, the text, the context;
                 the token pattern refuses names at validation; injection cases in both sets
Contract:        summarize.run (POST /v1/summarize), translate.run (POST /v1/translate) ADD; not breaking
Invariants:      INV-007..009, INV-011, INV-018, INV-030..033, INV-035, INV-037, INV-039, INV-042, INV-043
Blast radius:    SYSTEM on the branch (AI-005's migrations and port change ride ahead of this ticket in the same tree);
                 this ticket's own paths derive CAPABILITY — CONTRACT for the backend
Decision level:  2
ADR:             none new
```

## Changed
- `contract/{summarize,translate}.py` — the models; participant tokens as a pattern (`^p[0-9]{1,4}$`); the target optional in the model, required at the door
- `capabilities/summarize/{descriptor,schema,pipeline,postprocess,routes}.py`, `prompt_v1.md` — the thread as one fenced text, one line per item; the participant check (`ai.output.unsafe`), the word cap at 1.5 × target, headings and fences stripped, `covered_range`, a deterministic confidence
- `capabilities/translate/{descriptor,schema,pipeline,postprocess,quality,routes}.py`, `prompt_v1.md` — `require_target` at the door; `quality.py`: the script of a language, detection by dominant script, the Markdown skeleton, the kept spans (keys, links, code, placeholders); `structure_preserved` and `confidence` on the response
- `config/settings.py`, `app.py` — two capability groups; two routers
- `tools/{authored,evalkit,evalsets,evalsets_threads,thread_terms}.py` — the stand-ins (cue-based summaries; letter-by-letter script maps for translations), the registry rows, the set generators and their vocabulary
- `evals/{summarize,translate}/{set.jsonl,graders.py,thresholds.yaml,README.md}`, `tests/fixtures/providers/gemini/{summarize,translate}/` — sets v1 and authored fixtures
- `tests/unit/capabilities/{summarize,translate}/**`, `tests/unit/contract/test_{summarize,translate}.py`, `tests/contract/test_{summarize,translate}.py`
- `docs/`: ledgers (capabilities, errors, config, eval-sets, contracts changelog), `THREAT-004-summaries.md`, the capability lines

## Verify
```
$ make verify
ruff / mypy (267 files + each set's graders) / lint-imports   All checks passed! · Success · Contracts: 5 kept, 0 broken.
tools.checks.gate --skip coverage,budgets                     GATE GREEN (43 checks)
tools.api · oasdiff                                           api\openapi.yaml matches the app · no breaking change against main
pytest tests/architecture · pytest --cov                      24 passed · 406 passed in 35.73s · Total coverage: 99.43%
tools.checks.gate --only coverage                             GATE GREEN (1 checks)
pytest tests/storage                                          3 passed
make evals                                                    -- summarize v1 - 106 cases · 1.000 on every grader · overall 1.000 (0.97) · p95 5 ms · 561 micro-dollars
                                                              -- translate v1 - 94 cases · 1.000 on every grader · overall 1.000 (0.97) · p95 5 ms · 48 micro-dollars
                                                              -- search v1 · improve-story v1 · generate-children v1 unchanged
                                                              EVALS GREEN
tools.checks.gate --only budgets                              GATE GREEN (1 checks)
pip-audit / gitleaks / licences                               No known vulnerabilities found · no leaks found · GATE GREEN
selftest                                                      45/45 checks red on their plant
VERIFY GREEN
```
```
$ make ci
$ make ci     (python:3.12.14-slim, the workflow's steps verbatim)
All checks passed! · Success: no issues found in 267 source files · Contracts: 5 kept, 0 broken.
GATE GREEN (43 checks) · api/openapi.yaml matches the app · oasdiff: no breaking change against main
24 passed · 406 passed in 82.36s · Total coverage: 99.43% · GATE GREEN (1 checks)
pytest tests/storage: 3 passed
EVALS GREEN (summarize 1.000 · translate 1.000 · search recall@10 0.914, mrr 0.787 · improve-story 1.000 · generate-children 1.000) · GATE GREEN (1 checks)
No known vulnerabilities found · no leaks found · GATE GREEN (1 checks)
selftest: 45/45 checks red on their plant
VERIFY GREEN
```

## Eval and budget numbers
summarize set v1, prompt v1, `text-default`: **1.000 on every grader (schema_valid, tokens_only,
length_bounds, covered_range_correct, structure_clean, language_preserved, identifiers_kept,
no_forbidden_content, empty_when_nothing, status_changes_reflected); overall 1.000; p95 latency
5 ms; p95 cost 561 µ$** over 106 cases (58 comments / 48 thread; 18 Arabic; 8 empty; 8 injection).
translate set v1, prompt v1, `text-fast`: **1.000 on every grader (schema_valid, target_script,
detected_language_correct, structure_kept, spans_kept, no_name_like_introduced, length_bounds,
no_forbidden_content); overall 1.000; p95 latency 5 ms; p95 cost 48 µ$** over 94 cases (43 field /
51 title; en→ar and ar→en; 6 injection). Authored fixtures: cue-based summaries and letter-by-letter
script maps — the numbers prove the participant rule, the cap, the range, structure preservation,
the kept spans, the script rule and the graders, not the model's judgement or translation quality.
Planted regressions (each reverted, each red): the stand-in transliterating item keys →
`spans_kept 0.766`, `structure_kept 0.872`, `EVALS RED for translate`; the participant check
letting any token through → `test_check_participants_accepts_thread_and_status_tokens_only` red;
a 400-word completion against `target_words` 40 → the cap and `confidence` < 1 in
`test_summarize_run_caps_the_length_and_reports_the_range`.

## Decisions and questions
- D-020 proposed: participant tokens are a schema rule — `p1`…`p9999`, one per person per
  thread, chosen and mapped by the backend; a summary naming any other token is `ai.output.unsafe`;
  a name-like string in a comment is text, never an author (`Q-001` (a) made concrete; the token
  shape the card asked to propose).
- D-021 proposed: translation always names its target; the previous functions' inference (Arabic →
  English, else → Arabic) is a backend default, not a service rule (`target_language_required`).
- D-022 proposed: `structure_preserved` and `confidence` are computed from deterministic signals
  (`capabilities/translate/quality.py`) that the graders share; the backend reads them before
  replacing a Markdown field.
- No finding filed; no new question.

## Commit
Two proposals:
1. Files: `src/**`, `tools/**`, `tests/{unit,contract}/**`, `evals/{summarize,translate}/{graders.py,thresholds.yaml,README.md}`, `docs/**`, `brain/**`
   Proposed: `feat(summarize,translate): summaries by token and translations with structure kept`
2. Files: `api/openapi.yaml`, `evals/{summarize,translate}/set.jsonl`, `tests/fixtures/providers/gemini/{summarize,translate}/**`
   Proposed: `gen: contract document, sets and authored fixtures for summarize and translate v1`
Green light: given by the lead on 2026-09-21 — committed on local `main` in the proposed order (no remote yet)

## Next
The live recording of the five sets when the key arrives; the workflow and digest card.
