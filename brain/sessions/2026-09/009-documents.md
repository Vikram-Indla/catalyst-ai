# 009 — documents: hostile parsing, a second corpus, grounded answers

**Date:** 2026-09-22 · **Ticket:** AI-009 · **Capability or package:** documents, retrieval/parsers, retrieval/runner, platform/storage, propose-workflow (renamed), evals · **Author:** a contributor

## Read
`ARCH-006`, `ARCH-009`, `ADR-003`, `RULE-008`, `THREAT-005`, the threat-model template; the
backend's answer on the workflow engine's words (statuses `{key, name, category, initial,
order}`, transitions `{key, name, from, to, requires_reason}`, no approvals) — applied to
`propose-workflow` first, as a `CHANGE` before any consumer exists; the previous system's
`docintel-ingest` / `-analyze` / `-ask` / `-generate` / `-sync`, `kb-train`, `folio-ai-search`
and `_shared/{docintel,docx,pptx}.ts` for behaviour (a per-user embedding cache, page images
sent to a vision model, `mammoth` / `unpdf` / SheetJS run in the request process with no size,
depth, macro or script guard — `F-016`); the security notes of `pypdf`, `defusedxml`,
`python-docx` and `python-pptx` for the register rows.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-009
Capability:      documents v1.0.0 (ingest, ask, generate) · alias text-default · embed-default for the index ·
                 propose-workflow 1.0.0 → 1.1.0 (prompt v2, the engine's words added beside the old ones)
Inputs:          ingest: space_id, document_id, kind, format, filename?, title?, content_hash · INTERNAL; content_base64 (≤ 14 M) xor
                 text (≤ 200 k) · the declared data_class (RESTRICTED refused at the door)
                 ask: space_id, kinds[], k · INTERNAL; question (≤ 2 000) · CONFIDENTIAL; language? · PUBLIC
                 generate: brief (≤ 4 000), sources[] {id, title?, text ≤ 20 k} (1–40) · CONFIDENTIAL; target_words, language? · PUBLIC
Tenant boundary: organization_id on the request; the documents corpus rows carry it under the same RLS as work_items; the key is
                 <space_id>/<document_id> and every search leg filters on the space prefix; the cache key carries the whole request
Provider/model:  gemini · embed-default for chunks and questions; text-default for ask and generate (text-long deferred until a
                 live recording says forty sources of 20 000 characters need it)
Prompt version:  prompt_v1.md (system: groundedness and the data rules; developer: [mode:ask] / [mode:generate]; user fences)
Eval set:        evals/documents v1 · 92 cases · 8 graders (no_uncited_claims hard floor 1.0) · evals/documents-generate v1 ·
                 42 cases · 7 graders · evals/documents-ingest v1 · 19 cases · 4 graders (the parse matrix; expected refusals)
Budget:          p95 15 000 ms · 8 000 µ$ · timeout 20 000 ms (the parse deadline of the child) · index budgets of AI-006 apply
Failure mode:    ai.input.rejected{document_too_large | document_unsupported | document_malformed | document_timeout |
                 document_restricted} — one reason class, never a crash, never a partial index; ai.output.invalid{uncited_claim |
                 untraceable_entry} on any claim or section without a passage the service showed; not_found without a call when
                 retrieval is empty or under the score floor; ai.output.unsafe on a leaking line; the provider codes as before
Cache:           600 s over the whole classified request (ask and generate); ingest is idempotent by content_hash (unchanged)
Safety:          bytes parsed only in a killable child (deadline, address-space ceiling on POSIX, recursion limit, 64 MB answer);
                 container, entity, macro, script, traversal and size guards before any text; the extracted text scanned before
                 indexing; an instruction inside a page is text (the injected page in the corpus, injected questions and sources
                 in the sets); citations checked against the passages retrieved for this question; quotes ≤ 300 characters
Contract:        documents.ingest, documents.ask, documents.generate ADD; propose_workflow.run CHANGE, additive — `name` and
                 `order` beside `label` and `sort_order`, either spelling accepted on `existing`, `requires_approval` kept and
                 deprecated, the three removed at 1.2.0 (ARCH-004 §6); Corpus gains `documents`; oasdiff: no breaking change
Invariants:      INV-007..009, INV-011, INV-018, INV-030..033, INV-035, INV-037..039, INV-042, INV-043, INV-047; new INV-048
                 (groundedness), INV-049 (bounded parsing)
Blast radius:    SYSTEM — a migration (the documents corpus tables and policies), two dependencies (pypdf, defusedxml), a ruff
                 per-file ignore for the child's subprocess call, a mypy override for defusedxml; PLATFORM for the storage seam
                 (SearchScope.prefix) and the pipeline's settle hook; CAPABILITY for documents; CONTRACT for the backend
Decision level:  3 (the first capability that ingests whole documents)
ADR:             none new; ADR-003's dependency row carries pypdf and defusedxml (D-029 explains why not python-docx / python-pptx)
```

## Changed
- `propose_workflow` — 1.1.0, prompt v2: the model answers in the engine's words (`StatusBase` / `TransitionBase`, the schema it fills); the contract's `Status` and `Transition` carry `label`, `sort_order` and `requires_approval` as deprecated mirrors the service fills, `ExistingStatus` reads either spelling; the first cut renamed the fields outright and `oasdiff` refused it against `main` — the law's expand/contract path taken instead; stand-in, set and fixtures re-recorded; changelog `CHANGE`
- `platform/pipeline/stages.py` — `settle`: an optional stage after retrieve that answers without a call (ask uses it for `not_found`)
- `platform/storage/{rows,memory,postgres}.py`, `queries/search_*.sql` — `SearchScope.prefix`, applied on every leg (`starts_with(external_id, $n)`); `contract/search.py` — `Corpus` vs `SearchCorpus`
- `db/migrations/20260922100000_retrieval_documents.sql` — `index_documents_documents`, `embeddings_documents`, the same RLS and roles as the work-items pair
- `retrieval/corpora.py` (`DOCUMENTS`: 768 dims, chunks of 1 000 with 120 overlap, ≤ 200 000 characters), `retrieval/ingest.py` (a pluggable chunker), `retrieval/documents.py` (keys, windows led by a `§ A > B` heading line, `Passage`), `retrieval/grounding.py` (`Grounding`, `Retrieved.found` at the 0.15 floor, chunk-level fusion, `retrieve`)
- `retrieval/parsers/{port,text,office,pdf}.py` — one port (`Parsed`, `Block`, `ParserError(reason)`), the guards of the register; `retrieval/runner.py` — the child worker over JSON pipes: deadline → `document_timeout`, crash → `document_malformed`, address-space ceiling where the platform offers `resource` (imported by name so both paths are tested everywhere), recursion limit, bounded answer
- `contract/documents.py` — the three requests and responses, every field classified; `capabilities/documents/**` — descriptor, `ingest` (text formats in-process, bytes in the child, `document_restricted` from the scan, idempotent by hash), `ask` (parse → validate → retrieve → settle → assemble → call → check every claim → render `text [n]` → citations with quotes), `drafting` (every section cites a supplied source, `sources_insufficient` as the empty reason), `citations`, `schema`, `routes`, `prompt_v1.md`
- `config/settings.py`, `app.py` — the capability group and the router
- `tools/hostile.py` (writes the hostile and benign corpora), `tools/{document_terms,document_traps,evalsets_documents,authored_documents}.py`, `tools/{authored,evalkit,evals}.py` (the stand-ins dispatched before the translation marker; `ingest_corpus` setup; a case may expect a refusal — `F-017`)
- `evals/{documents,documents-generate,documents-ingest}/**`, `tests/fixtures/documents/{benign,hostile}/**`, `tests/fixtures/providers/gemini/{documents,documents-generate,documents-ingest,propose-workflow}/**`
- `tests/unit/retrieval/**` (the hostile corpus test with the 15 s limit, the runner, windows, grounding), `tests/unit/retrieval/parsers/**` (a property test per parser), `tests/unit/capabilities/documents/**`, `tests/unit/contract/test_documents.py`, `tests/contract/test_documents.py`, `tests/storage/test_postgres.py` (the documents corpus under RLS and the space prefix)
- `docs/`: `ADR-003` dependency row; ledgers (capabilities, errors, config, eval-sets, invariants, parsers — new, contracts changelog); `THREAT-005` rows 10–16; the runbook line; `pyproject.toml`, `uv.lock`, `ruff.toml`, `mypy.ini`

## Verify
```
$ make verify
ruff / mypy (385 files + each set's graders) / lint-imports   All checks passed! · Success · Contracts: 5 kept, 0 broken.
tools.checks.gate --skip coverage,budgets                     GATE GREEN (43 checks) · report: contract has 14 files (F-015), retrieval has 12 files (F-018)
tools.api · oasdiff                                           api\openapi.yaml matches the app · no breaking change against main
pytest tests/architecture · pytest --cov                      24 passed · 633 passed in 90.33s · Total coverage: 99.45%
tools.checks.gate --only coverage                             GATE GREEN (1 checks)
pytest tests/storage                                          4 passed
make evals                                                    -- documents v1 - 92 cases · 1.000 on every grader · overall 1.000 (0.97) · p95 11 ms · 339 micro-dollars
                                                              -- documents-generate v1 - 42 cases · 1.000 on every grader · overall 1.000 (0.97) · p95 4 ms · 1 234 micro-dollars
                                                              -- documents-ingest v1 - 19 cases · 1.000 on every grader · overall 1.000 (1.0) · p95 1 124 ms · 8 micro-dollars
                                                              -- propose-workflow v1 (prompt v2) - 46 cases · 1.000 on every grader · p95 4 ms · 1 432 micro-dollars
                                                              -- release-notes · generate-tests · post-mortem · summarize · translate · search · improve-story · generate-children unchanged
                                                              EVALS GREEN
tools.checks.gate --only budgets                              GATE GREEN (1 checks)
pip-audit / gitleaks / licences                               No known vulnerabilities found · no leaks found · GATE GREEN
selftest                                                      45/45 checks red on their plant
VERIFY GREEN
```
```
$ make ci
$ make ci     (python:3.12.14-slim, the workflow's steps verbatim)
All checks passed! · Success: no issues found in 385 source files · Contracts: 5 kept, 0 broken.
GATE GREEN (43 checks) · api/openapi.yaml matches the app · oasdiff: no breaking change against main
24 passed · 633 passed in 202.52s · Total coverage: 99.45% · GATE GREEN (1 checks)
pytest tests/storage: 4 passed
EVALS GREEN (documents 1.000 · documents-generate 1.000 · documents-ingest 1.000 · propose-workflow 1.000 · release-notes 1.000 · generate-tests 1.000 · post-mortem 1.000 · summarize 1.000 · translate 1.000 · search recall@10 0.914, mrr 0.787 · improve-story 1.000 · generate-children 1.000) · GATE GREEN (1 checks)
No known vulnerabilities found · no leaks found · GATE GREEN (1 checks)
selftest: 45/45 checks red on their plant
VERIFY GREEN
```

## Eval and budget numbers
documents (ask) set v1, prompt v1, `text-default`: **1.000 on every grader (schema_valid,
no_uncited_claims, citations_resolve, not_found_on_traps, answer_grounded, kinds_respected,
no_forbidden_content, language_preserved); overall 1.000; p95 latency 11 ms; p95 cost
339 µ$** over 92 cases (39 answerable questions, each once plain and once kind-filtered;
8 filter traps; 10 traps — the other space, the page that is not there; 6 injected questions;
one injected page in the corpus of 12).
documents-generate set v1, prompt v1, `text-default`: **1.000 on every grader (schema_valid,
every_section_cites, sources_used, length_bounds, empty_when_thin, no_forbidden_content,
language_preserved); overall 1.000; p95 latency 4 ms; p95 cost 1 234 µ$** over 42
cases (2–5 sources; 1 thin; 1 injected source).
documents-ingest set v1, no prompt, `embed-default`: **1.000 on every grader (state_as_expected,
chunks_present, headings_seen, versions_named); overall 1.000; p95 latency 1 124 ms (the child process)** over 19
cases (5 benign formats, the same file again → `unchanged`, 12 hostile refusals each with its
class inside the limit, 1 injected page indexed as text).
Authored fixtures: the ask stand-in ranks the retrieved sentences by overlap with the question
and cites the passage each came from, or says `not_found`; the draft stand-in writes one section
per source in its own words — the numbers prove the retrieval, the space prefix, the settle
stage, the claim check, the rendering, the section rule and the graders, not the models' prose.
Planted regressions (each reverted, each red): the ask stand-in citing nothing → every
answerable case refused with `uncited_claim`, `EVALS RED for documents`; the memory seam
ignoring `scope.prefix` → the other-space traps answered, `not_found_on_traps` and
`no_forbidden_content` 0.957, `EVALS RED for documents`, and
`test_only_the_space_is_read_and_passages_carry_provenance` red; the macro guard removed →
`macro.docx` indexed, `EVALS RED for documents-ingest`; `check_claims` dropped from the
response → `test_documents_ask_refuses_an_uncited_answer_and_stays_in_the_space` red through
the app (a 200 where a 502 `uncited_claim` is owed). The stand-in made to answer without
evidence stayed green: it finds no supporting sentence on a trap because the settle stage never
calls it — the floor holds before the model is asked.

## Decisions and questions
- D-029 proposed: Word and PowerPoint are read with `zipfile` + `defusedxml`, not the two convenience libraries `ADR-003` planned; `pypdf` for the PDF text layer; no OCR in v1 (a register row says what it would need).
- D-030 proposed: documents are a second corpus of the same index, keyed `<space>/<document>`, the space a prefix on every search leg; no second store.
- D-031 proposed: groundedness is a schema — claims with chunk ids, `text [n]` rendered by the service, uncited or untraceable refused, `not_found` without a call under the floor.
- F-016: where the previous parsers trusted the file; F-017: the eval harness could not expect a refusal — it can now; F-018: `retrieval/` is reported at twelve modules (a report, as `contract/` in F-015).
- Q-010 to the backend: the `kind` values the wiki and folio modules will send, and what one `space_id` is.

## Commit
Two proposals (after AI-008's two):
1. Files: `src/**`, `tools/**`, `tests/{unit,contract,storage}/**`, `evals/{documents,documents-generate,documents-ingest}/{graders.py,thresholds.yaml,README.md}`, `evals/propose-workflow/README.md`, `docs/**`, `brain/**`, `db/migrations/20260922100000_retrieval_documents.sql`, `pyproject.toml`, `uv.lock`, `ruff.toml`, `mypy.ini`
   Proposed: `feat(documents): bounded parsing, a documents corpus and grounded answers with citations`
2. Files: `api/openapi.yaml`, `evals/{documents,documents-generate,documents-ingest,propose-workflow}/set.jsonl`, `evals/documents/corpus.jsonl`, `tests/fixtures/documents/**`, `tests/fixtures/providers/gemini/{documents,documents-generate,documents-ingest,propose-workflow}/**`
   Proposed: `gen: contract document, sets, corpora and authored fixtures for documents`
Green light: awaited

## Next
The backend's answer to `Q-010`; the assistant card (reuses `documents.ask`); the live recording of the twelve sets when the key arrives.
