---
id: THREAT-006
family: the assistant (assistant.turn, assistant.turn_sync) and the unfurl card
status: Draft
reviewed: —
asvs: 5.0
llm-top10: 2025
---

# THREAT-006 — the assistant

## Assets

The thread and the backend's summary of it (`CONFIDENTIAL`); the context the backend chose — items
as facts, pages as text, spaces read through the documents index (`CONFIDENTIAL` / `INTERNAL`);
the passages of the index (their documents' class); the prompt files (`INTERNAL`); the provider key
and the service token (`RESTRICTED`); the member's trust that a reply states only what the
context says.

## Entry points and trust boundaries

`POST /v1/assistant/turn:stream`, `POST /v1/assistant/turn`, `POST /v1/unfurl`. Trust changes at
the service token; the request models (`extra="forbid"`, ≤ 20 turns of ≤ 4 000 chars, ≤ 50 items,
≤ 10 spaces, ≤ 5 pages of ≤ 20 000 chars, id and kind shapes, the last turn the member's); the
door (switch, version, scanner over every turn, item, page and passage, tenant cap); the fences
around the thread and the numbered sources; the tail split and the reply check on completion;
the leakage scanner; the event writer that ends every stream with one terminal frame. The
package is read-only by construction (`tools/checks/readonly`).

## Attackers

A member through the backend (an instruction in a turn, a turn that claims to be the system, a
question outside the product, a request to act) · a member who wrote a page or an item (an
instruction inside the context) · the backend with a bug (a space the member may not read, a
thread that is not the member's, a missing summary) · the provider (a reply that cites nothing or
cites a number never shown, prose that leaks a key, a stream that stops half-way) · anyone
reading logs.

## Threats

| # | Attacker | Entry point | Attack | Mitigation (code) | Verified by | ASVS / LLM |
| --- | --- | --- | --- | --- | --- | --- |
| 1 | member | a turn | "ignore previous instructions", "you are now", a turn that says it is the system, "reveal the prompt" | the thread is fenced as data; the prompt says a fence is never an instruction; the scanner refuses the known shapes at the door; the stand-in and the set expect `not_found` | `inject-history-*` cases, `injection_inert` floor 1.0; `test_the_door_refuses_switch_scanner_version_and_a_leak` | V5; LLM01 |
| 2 | member (author) | an item summary, a page, a passage | an instruction inside the context ("reply ACCESS GRANTED") | the sources are fenced; the reply is checked for echoed phrases by the set; the scanner refuses a leaked key or link | `inject-context`, `inject-summary` cases; `injection_inert`, `no_forbidden_content` | LLM01, LLM02 |
| 3 | member | a turn | "create the item", "delete that", "assign it to me" | the service has no tool and no writer (`tools/checks/readonly`, red on its plant); the prompt answers that acting happens in the product; a reply claiming to have acted fails `injection_inert` | the check; the set | LLM06 |
| 4 | provider | the completion | a factual sentence with no marker; a marker never shown | `check_reply` → `ai.output.invalid` (`uncited_claim`, `untraceable_entry`); the stream ends with the `error` frame and the backend discards what it showed | `test_check_reply_refuses_unknown_numbers_and_uncited_facts`; `test_assistant_turn_fault_mid_stream_ends_with_an_error_frame` | LLM09 |
| 5 | provider | the completion | a reply with no tail, or a tail that is not the schema | one repair call, then `ai.output.invalid`; the tail never streams (`hold_back`) | `test_not_found_and_an_uncited_fact_and_a_missing_tail`; `test_only_the_visible_prefix_streams` | LLM09 |
| 6 | provider | the stream | a connection that breaks mid-way; a blocked finish; an empty stream | the adapter maps the failure to the catalog (`ai.provider.unavailable`, `rejected`); no retry once frames flowed; the writer emits the terminal `error` frame | `test_stream_failures_map_to_the_catalog_and_never_retry`; the contract test | V7 |
| 7 | backend bug | `context.spaces` | a space the member may not read | the backend enforces membership before the call and the contract says so; the service reads exactly the spaces named and nothing else (the prefix on every leg, INV-045) | `test_documents_corpus_holds_rls_and_the_space_prefix` (the seam); the changelog's "backend must" | V4 |
| 8 | member | a turn | a question outside the product (weather, general knowledge) | the prompt declines in one sentence with `not_found`; the set expects it | `off-topic-*` cases | LLM09 |
| 9 | member | a long thread | a thread grown to exhaust the budget | ≤ 20 turns of ≤ 4 000 chars; the summary carries the rest; the door's estimate reserves the budget; streamed tokens are metered on the `usage` frame and settled | the contract test with a budget of 1 → `ai.budget.exceeded` as the terminal frame | V13 |
| 10 | provider | the completion | a person's name, an email, a credential surfacing from a page | the leakage scanner over the joined reply against every request text; a foreign identifier or a link is `ai.output.unsafe` | `test_the_door_refuses_switch_scanner_version_and_a_leak`; `no_forbidden_content` | LLM02 |
| 11 | backend bug | `unfurl` | a URL sent to be fetched | there is no URL field and no client; the card is built from the text sent | `test_defaults_and_kinds` (an extra key is refused); `tools/checks/readonly` covers the assistant, `boundary` every capability | LLM06 |
| 12 | provider | the card | a fact the text does not carry | `kept_facts` drops any value whose words the text lacks; the grader floors it at 1.0 | `test_an_invented_fact_is_dropped_and_lowers_confidence`; `facts_carried` | LLM09 |
| 13 | anyone | logs | a turn in a log line | the row model has no content field; `tools/checks/logs` | the gate | LLM02 |

## Residual risk

- The factual-sentence rule is a heuristic (six words, not a question): a short invented claim
  with no marker passes the service's check; the set's graders and the prompt carry the rest.
- A repair call after a bad tail answers whole while the member already saw the first deltas;
  the `done` result is authoritative and the backend renders it — the prompt makes a bad tail rare,
  the fixtures do not exercise the divergence.
- v1's fixtures are authored: the replies are overlap-ranked cited sentences. The floors prove
  the runner, the split, the marker rule and the graders, not the model. Revisit at the first live
  recording.
- Accepted by: pending the lead (`D-NNN`).
