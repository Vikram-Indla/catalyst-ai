---
id: THREAT-004
family: summaries and translation (summarize, translate; later summarize-standup, digest, release-notes, post-mortem)
status: Draft
reviewed: —
asvs: 5.0
llm-top10: 2025
---

# THREAT-004 — summaries and translation

## Assets

The thread's comments and the fields sent for translation (`CONFIDENTIAL`); the mapping from
participant tokens to people (never here — it stays in the backend; `RESTRICTED` there); the
prompt files (`INTERNAL`); the provider key and the service token (`RESTRICTED`).

## Entry points and trust boundaries

`POST /v1/summarize`, `POST /v1/translate`. Trust changes at the service token; the request
models (`extra="forbid"`, ≤ 200 items of ≤ 4 000 chars, the token pattern `p1`…`p9999`, ≤ 20 000
chars per field, ≤ 800 of context, BCP 47 tags); the door (switch, version, scanner over every
text, tenant cap); the fences around the thread, the status changes, the text and the context;
the output schema; the leakage scanner; the participant check; the word cap; the target rule.

## Attackers

A member through the backend (an instruction or a name inside a comment; "translate this and
also…") · the backend with a bug (a name sent as a token — refused by the pattern; a missing
target) · the provider (a summary naming someone the thread does not; a translation carrying a
foreign key or a link; a translation left in the source script) · a tenant script (long threads,
long fields).

## Threats

| # | Attacker | Entry point | Attack | Mitigation (code) | Verified by | ASVS / LLM |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | provider / member | the completion | a summary names a person the thread did not, by token or by name | tokens must match `p\d+`; `check_participants` refuses any token outside the thread (`ai.output.unsafe`, `participant_not_in_thread`); the `tokens_only` grader also refuses name-like words the thread lacks | `test_a_summary_naming_an_unknown_participant_is_unsafe`; contract test; eval floor 1.0 | LLM02, LLM09 |
| 2 | backend bug | `items[].participant` | a real name sent as a token | the pattern refuses it at validation (400) | `test_invalid_requests` (name as token) | V5 |
| 3 | member | a comment, a field | an instruction inside the data | fences with marker stripping; the data rule in both system segments; the output schema cannot carry commands; the leakage scanner | eval `*-injection-*`; `injection_inert` by construction (the graders still apply) | LLM01 |
| 4 | provider | the completion | a summary far longer than asked, or with headings and fences | `cap_words` at 1.5 × the target; `strip_structure`; the `length_bounds` and `structure_clean` graders | `test_cap_words_cuts_and_marks`; contract test `caps_the_length` | — |
| 5 | backend bug | `translate.run` | a translation without a target | `require_target` refuses at the door with `target_language_required`, before any call | `test_a_request_without_a_target_is_refused_before_any_call` | V5 |
| 6 | provider | the completion | a translation carrying a foreign key, a link, a secret, or a fence echo | the leakage scanner (`ai.output.unsafe`); `spans_kept` and `no_forbidden_content` floors 1.0 | `test_a_translation_with_a_foreign_key_is_unsafe` | LLM02, LLM05 |
| 7 | provider | the completion | a translation left in the source script, or with the Markdown broken | `in_target_script` and `structure_preserved` drive `confidence` and the graders; the backend reads `structure_preserved` | `test_confidence_penalises_script_structure_spans_and_length`; eval floors | LLM09 |
| 8 | tenant script | items, text | cost runaway | request bounds, the total-size door, the tenant spend and concurrency caps, `max_output_tokens` | contract tests `too_large`, `budget_exceeded` | LLM10 |
| 9 | anyone | logs | thread text in a log line | the row model has no content field; `tools/checks/logs` | `test_row_has_no_content_field`; the gate | LLM02 |

## Residual risk

- The name-like check is a heuristic on capitalised words: a lower-case name or one already in
  the thread passes. The token rule is the guarantee; the heuristic catches the model inventing.
- v1's fixtures are authored: the summaries are cue-based and the translations are script maps.
  The floors prove the rules, not the model. Revisit at the first live recording.
- Accepted by: pending the lead (`D-NNN`).
