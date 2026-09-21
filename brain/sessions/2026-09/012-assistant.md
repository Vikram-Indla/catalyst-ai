# 012 — the assistant: a streamed, grounded turn; the unfurl card; the chat summary

**Date:** 2026-09-23 · **Ticket:** AI-010 · **Capability or package:** assistant, unfurl, summarize (mode chat), platform/pipeline/streaming, platform/httpserver/sse, providers/gemini/streaming, providers/recorded, contract, tools/checks/readonly, evals · **Author:** a contributor

## Read
`ARCH-002`, `ARCH-004 §4` (the frames), `ADR-007` (a stream is synchronous SSE), `RULE-008`,
`THREAT-004`, `THREAT-005`; the previous system's `caty-chat` (seven persona prompts over the last
ten turns, no data), `ai-admin-assistant` (intents parsed into a typed plan, then executed against
the profile and role tables by the function itself), `ai-tm-assist` (a test-case refiner, `draft_only`),
`chat-summarize` (two to four sections: activity, decisions and action items, open questions),
`chat-unfurl` (fetched the linked page's HTML for its `og:` tags), `ai-theme-prewarm` (a nightly
cron filling a per-member theme cache) — `F-021`, `F-022`; the port's `stream()` stub; the
recorded transport; the documents capability's grounding as the thing to reuse.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-010
Capability:      assistant v1.0.0 (turn as SSE, turn_sync whole) · unfurl v1.0.0 · summarize 1.0.0 → 1.1.0 (mode chat, prompt v2,
                 set v2) · aliases text-default; embed-default for the spaces
Inputs:          turn: history[] {role, text ≤ 4 000} 1–20 (the last the member's) · CONFIDENTIAL; summary? ≤ 2 000 · CONFIDENTIAL;
                 context {items[] ≤ 50 (id, key?, kind, title, status?, summary?), spaces[] ≤ 10 (space_id, title?), pages[] ≤ 5
                 (id, title?, text ≤ 20 000)} · CONFIDENTIAL; language? · PUBLIC
                 unfurl: kind, id, status? · INTERNAL; title, text? ≤ 20 000 · CONFIDENTIAL; language? · PUBLIC
                 summarize chat: the existing items[] with participant tokens · CONFIDENTIAL
Tenant boundary: organization_id on the request; the spaces are read with the documents corpus' prefix under the same RLS; the
                 cache key (whole form and unfurl) carries the classified request; a stream is never cached
Provider/model:  gemini · text-default streamed for the turn (streamGenerateContent, alt=sse), whole for turn_sync and unfurl;
                 embed-default for the spaces
Prompt version:  assistant prompt_v1.md (system: the sources rule, no acting, the tail; developer: the language; user: thread,
                 sources); unfurl prompt_v1.md; summarize prompt_v2.md (adds [mode:chat])
Eval set:        evals/assistant v1 · 83 turns · 9 graders (no_uncited_claims, injection_inert floors 1.0) · evals/unfurl v1 ·
                 6 cards · 4 graders · evals/summarize v2 · 246 cases (+48 chat) · 15 graders
Budget:          assistant p95 12 000 ms · 6 000 µ$ · timeout 20 000 ms · unfurl p95 4 000 ms · 1 000 µ$ · timeout 10 000 ms
Failure mode:    a stream ends with exactly one terminal frame: done or error (the envelope); a provider failure mid-stream, a
                 refused reply (uncited_claim, untraceable_entry), a missing tail after one repair, a leak, an exhausted budget —
                 each is the error frame and the backend discards what it showed; the whole form returns the envelope as every
                 capability; unfurl drops a fact the text does not carry, never returns it
Cache:           turn_sync 300 s; unfurl 3 600 s; the stream none (a turn is not idempotent)
Safety:          the door's scanner over every turn, item, page and passage; fences; the read-only package (no client, socket,
                 writer or ingest path — tools/checks/readonly, red on its plant); the prompt's rules (no acting, sources only,
                 decline off-topic); the reply check; the leakage scanner over the joined prose; injected turns, contexts and a
                 thread summary in the set; the frames' data shape documented as StreamEnvelope
Contract:        assistant.turn, assistant.turn_sync, unfurl.run ADD; summarize.run CHANGE (additive: mode chat, chat[]); the
                 documented frame shape; no path version moves; oasdiff: no breaking change
Invariants:      INV-002, INV-007..009, INV-011, INV-018, INV-030..033, INV-035, INV-037..039, INV-042, INV-043, INV-045, INV-048;
                 new INV-050 (the assistant is read-only and cites), INV-051 (one terminal frame)
Blast radius:    PLATFORM — the streaming runner, the event writer, the adapter's stream, the recorded transport's raw fixtures;
                 CAPABILITY for assistant, unfurl and summarize; CONTRACT for the backend; a new gate check (46)
Decision level:  3 (the first streaming contract; conversational state in the request)
ADR:             none new; ADR-007 already places streams as synchronous SSE
```

## Changed
- `contract/assistant.py` — `TurnRequest` (history, summary, context, language; the last turn the member's), `TurnResponse` (reply with `[n]` markers, `sources[] {marker, kind, source_id, citation?}`, not_found, confidence); `contract/streaming.py` — `DeltaFrame`, `CitationFrame`, `UsageFrame`, `DoneFrame`, `ErrorFrame`, the discriminated `Frame`, `StreamEnvelope`; `contract/unfurl.py`; `contract/summarize.py` — `SummarizeMode.CHAT`, `ChatSection`, `SummarizeResponse.chat[]`, `CHAT_HEADINGS`
- `providers/gemini/streaming.py` (data lines → delta frames, the last chunk's usage and model, a blocked reason raised, an empty stream a shape error), `providers/gemini/adapter.py` — `stream()` real (`streamGenerateContent?alt=sse`, the breaker and the status mapping, never a retry once frames flowed); `providers/recorded.py` — `raw` fixtures replayed verbatim, `write_raw_fixture`; `providers/faults.py` — a raw body
- `platform/pipeline/streaming.py` — `run_streaming` (the same stages; the call replaced by the provider's frames; `visible` decides what streams; `hold_back` keeps a marker cut short out of sight; `validate_output` and `postprocess` on completion; a settled run yields `done` without a call), `Event`; `platform/httpserver/sse.py` — one event per frame named by its kind, a raised error becomes the terminal frame, a stream without one is a defect, `stream_response`
- `capabilities/assistant/**` — descriptor (kind `stream`), `pipeline` (parse → validate → retrieve over the spaces with the documents' grounding, k 6 per space, 12 in all → assemble with the thread and the numbered sources fenced → call → split prose and tail with one repair → scan → check the reply → respond; `run` whole, `stream` as events), `sources` (numbering; markers; `check_reply`: an unknown marker is `untraceable_entry`, a factual sentence without one `uncited_claim`; `sources_cited`), `schema` (the `---` marker, `Tail`, `visible`, `split`), `reply`, `frames`, `routes` (the SSE route with the documented event stream and its example; the whole route), `prompt_v1.md`
- `capabilities/unfurl/**` — a card from supplied content; `kept_facts` drops any value whose words the text lacks; `capabilities/summarize/**` — 1.1.0, prompt v2, `chat_sections` (the four fixed headings in order), `lines_of` over the three shapes, `chat-summarize` retired here
- `config/settings.py`, `app.py` — two capability groups, two routers
- `tools/checks/readonly.py` (+ its plant; `rules.READ_ONLY_CAPABILITIES`; CHECKS now 46), `tools/authored_assistant.py` (the turn, the card and the chat sections), `tools/authored_envelope.sse_of`, `tools/record.py` (a streamed call recorded as the event-stream text, authored or live), `tools/evalsets_assistant.py`, `tools/evalsets_threads.py` (chat cases), `tools/evalkit.py` (the streaming pipeline for the set; the registry rows), `tools/authored.py` (dispatch on `<<<sources>>>` and `<<<title>>>` before the rest)
- `evals/{assistant,unfurl}/**`, `evals/summarize/{graders.py (chat_shape), thresholds.yaml, README.md, set.jsonl}`, `tests/fixtures/providers/gemini/{assistant (raw), unfurl, summarize}/**`
- `tests/unit/{contract,providers/gemini,providers,platform/pipeline,platform/httpserver,capabilities/assistant,capabilities/unfurl,capabilities/summarize}/**`, `tests/contract/test_{assistant,unfurl}.py`; the `ScriptedProvider` double streams
- `docs/`: `THREAT-006-assistant.md` (13 rows), `RULE-006` (the read-only row), ledgers (capabilities — the assistant, the unfurl card, summarize 1.1.0, `ai-theme-prewarm` dropped; errors; config; eval-sets; invariants INV-050, INV-051; contracts changelog), the runbook lines; brain D-032..D-034, F-021, F-022, Q-011

## Verify
```
$ make verify
ruff / mypy (434 files + each set's graders) / lint-imports   All checks passed! · Success · Contracts: 5 kept, 0 broken.
tools.checks.gate --skip coverage,budgets                     GATE GREEN (44 checks) · report: contract 17 files (F-015), retrieval 12 files (F-018)
tools.api · oasdiff                                           matches the app · no breaking change against main
pytest tests/architecture · pytest --cov                      24 passed · 701 passed in 161.15s · Total coverage: 99.44% · GATE GREEN (1 checks)
pytest tests/storage · make evals · budgets                   4 passed · EVALS GREEN — assistant 1.000 (83) · unfurl 1.000 (6) · summarize v2 1.000 (246) ·
                                                              the eleven other sets unchanged · GATE GREEN (1 checks)
pip-audit / gitleaks / licences · selftest                    No known vulnerabilities found · no leaks found · GATE GREEN · 46/46 red on their plant
VERIFY GREEN
```
```
$ make ci
$ make ci     (python:3.12.14-slim, the workflow's steps verbatim, the named volumes warm)
All checks passed! · Success: no issues found in 434 source files · Contracts: 5 kept, 0 broken.
GATE GREEN (44 checks) · oasdiff: no breaking change against main
Total coverage: 99.44% · GATE GREEN (1 checks) · pytest tests/storage: 4 passed
EVALS GREEN (assistant 1.000 · unfurl 1.000 · summarize 1.000 · documents 1.000 · documents-generate 1.000 · documents-ingest 1.000 ·
propose-workflow 1.000 · release-notes 1.000 · generate-tests 1.000 · post-mortem 1.000 · translate 1.000 · search recall@10 0.914, mrr 0.787 ·
improve-story 1.000 · generate-children 1.000) · GATE GREEN (1 checks)
No known vulnerabilities found · no leaks found · GATE GREEN (1 checks)
selftest: 46/46 checks red on their plant
VERIFY GREEN
stamp: tree a5306cfa666a in python:3.12.14-slim at 2026-09-21T17:09:26+00:00 -- green            (wall 1 744 s)
```

## Eval and budget numbers
assistant set v1, prompt v1, `text-default`, through the streaming path: **1.000 on every grader
(schema_valid, no_uncited_claims, citations_resolve, not_found_on_traps, answer_grounded,
follow_ups_resolve, injection_inert, no_forbidden_content, language_preserved); overall 1.000; p95
latency 19 ms; p95 cost 211 µ$** over 83 turns (38 over the space, 10 follow-ups, 6 over items, 5
over supplied pages, 2 contradicted threads, 2 injected contexts, 10 traps, 4 injected turns, 4
off-topic, 2 without context).
unfurl set v1, prompt v1, `text-default`: **1.000 on every grader (schema_valid, facts_carried,
status_kept, no_forbidden_content); overall 1.000; p95 latency 4 ms; p95 cost 30 µ$** over 6 cards.
summarize set v2, prompt v2, `text-default`: **1.000 on every grader including `chat_shape`;
overall 1.000; p95 latency 6 ms; p95 cost 1 028 µ$** over 246 cases (48 chat).
Authored fixtures: the turn stand-in answers the last turn from the numbered sources by stemmed
word overlap and cites each sentence it keeps, says not found on an instruction, an off-topic cue
or no overlap; the fixtures are the event-stream text verbatim, so the numbers prove the
streaming runner, the tail split, the marker rule, the sources, the frames and the graders — not
a model's prose. Planted regressions (each reverted, each red): the turn stand-in citing nothing → every answerable turn refused with `uncited_claim` (`raised Error ai.output.invalid` on 61 cases), `EVALS RED for assistant`; `check_reply` dropped from the pipeline → `test_not_found_and_an_uncited_fact_and_a_missing_tail` and `test_assistant_turn_fault_mid_stream_ends_with_an_error_frame` red (a 200 where a refusal is owed); the runner streaming the whole completion instead of the visible prose → the tail leaks into the deltas and `test_only_the_visible_prefix_streams`, `test_stream_yields_the_prose_then_usage_and_the_same_response`, `test_assistant_turn_streams_deltas_citations_usage_and_done` red; the read-only check on its plant → `red  readonly (3 on plant)` in the selftest.

## Decisions and questions
- D-032 proposed: prose streams, a structured tail never does; `done` is authoritative, `error` discards.
- D-033 proposed: the provider streams for real; fixtures are raw event streams; no retry once frames flowed.
- D-034 proposed: the assistant's grounding is the documents capability's; markers name `sources[]` by number and are never renumbered.
- F-021: what the three previous functions were; F-022: `ai-theme-prewarm` was a cron cache, not a UI concern.
- Q-011 to the lead and the backend: whether the admin commands come back as backend features.
- A note for the reader of the card that cut this work: it named the frames `start … end`; `ARCH-004 §4` names them `delta, citation, usage, done | error`, and the page wins — no `start` frame, the first `delta` starts.

## Commit
Two proposals:
1. Files: `src/**`, `tools/**`, `tests/{unit,contract}/**`, `evals/{assistant,unfurl}/{graders.py,thresholds.yaml,README.md}`, `evals/summarize/{graders.py,thresholds.yaml,README.md}`, `docs/**`, `brain/**`
   Proposed: `feat(assistant): a streamed grounded turn, the unfurl card, the chat summary`
2. Files: `api/openapi.yaml`, `evals/{assistant,summarize,unfurl}/set.jsonl`, `evals/assistant/corpus.jsonl`, `tests/fixtures/providers/gemini/{assistant,summarize,unfurl}/**`
   Proposed: `gen: contract document, sets and fixtures for the assistant, unfurl and chat`
Green light: awaited

## Addendum — the stamp after the push
The push of the two commits ran the pipeline in the main checkout although `make ci` had stamped the tree
minutes before: the stamp's hash was not a pure function of the files on disk (F-023 — a deleted-but-uncommitted
file hashed as "missing", then vanished from the listing after the commit; and files hashed through git's
filters). `tree_hash` now takes only the files that exist, each as git would store it (the first cut hashed raw bytes and made a CRLF main checkout disagree with the LF worktree — its push ran the pipeline once more, and the second cut normalises); `test_the_tree_hash_does_not_move_when_a_change_is_committed`
commits a deletion and a CRLF file and sees the hash hold. Proposals: `build(stamp): hash the files on disk, so a commit never moves it`, then `build(stamp): hash as git stores, so both checkouts agree`;
the push of the second is the proof — it should skip.

## Next
The retirement pass (AI-011); Q-011; the live recording of the fourteen sets when the key arrives.
