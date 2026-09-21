---
id: ARCH-003
title: Capabilities and the pipeline shape
status: Locked
version: 1.0.1
owner: AI service lead
created: 2026-09-18
---

# ARCH-003 — Capabilities and the pipeline shape

## 1. A capability is a package

`src/catalyst_ai/capabilities/<name>/` is one capability: one *concern* in the contract — usually
one operation, sometimes the few operations that concern needs (an index is written, deleted and
searched) — one pipeline per operation, one or more versioned prompt files, one output schema
family, one eval set under `evals/<name>/`, one budget. The package is the unit of ownership, of
versioning (`capability_version`), of the kill switch, and of the ledger row; its operations share
the descriptor, the set and the budget. (Reworded from "one operation" on 2026-09-21, `D-023`.) Two capabilities never import
each other (`ARCH-012 §2`); what they share lives in `platform/` or `retrieval/` under a name.

```
capabilities/<name>/
  __init__.py       the public surface: `run(request) -> Result` and the capability descriptor
  descriptor.py     name, version, budget, prompt version, eval set version, data classes, kill-switch key
  pipeline.py       the stages in order; no provider call outside `call`
  schema.py         the output model the provider's text must validate against
  prompt_v1.md      the prompt, versioned, with the header RULE-008 §1 requires
  postprocess.py    deterministic transforms after validation (optional)
  routes.py         the FastAPI router: the concern's operations, thin, pydantic in and out
```

## 2. The pipeline — seven stages, one sampled

Every capability runs the same stages in the same order. Six are deterministic and unit-tested
with plain values; one samples the model and is tested with recorded fixtures.

| # | Stage | Does | Fails with | Deterministic |
| --- | --- | --- | --- | --- |
| 1 | **parse** | the typed request model (already validated by FastAPI against the contract) is turned into the pipeline's input value | `validation.invalid_input` | yes |
| 2 | **validate** | data classes at the door; the safety scanner (`ARCH-009 §2`); size limits; the kill switch; the tenant budget (`ARCH-008 §2`) | `ai.input.rejected`, `ai.capability.disabled`, `ai.budget.exceeded` | yes |
| 3 | **retrieve** | context the capability needs from the service's own index — similar items, document chunks — per tenant, with provenance (`ARCH-006`) | `ai.index.unavailable` | yes |
| 4 | **assemble** | the prompt file, the retrieved context and the delimited user segments become one request to the port: system, developer and user segments explicit, untrusted text marked as data (`RULE-008 §2`) | — | yes |
| 5 | **call** | the one provider call through the `Provider` port, with the capability's timeout, the adapter's retries and circuit breaker, the cache in front (`ARCH-008 §3`) | `ai.provider.unavailable`, `ai.provider.timeout`, `ai.provider.rejected` | **no** — recorded in tests |
| 6 | **validate output** | the completion is parsed against `schema.py`; the leakage scanner runs (`ARCH-009 §3`); one repair attempt at most, then failure | `ai.output.invalid` | yes |
| 7 | **post-process** | deterministic transforms: trimming, ordering, scoring, mapping to the response model with `capability_version`, `prompt_version`, `model`, `usage`, `confidence`, `provenance` | — | yes |

`pipeline.py` is a straight sequence of these calls. A branch on the *content* of a completion
("if the model said X, do Y") is a rule and belongs in a grader or a schema, never in the
pipeline; `tools/checks/pipeline` refuses a pipeline whose stages appear out of order or that
calls the port outside stage 5.

## 3. Versions travel

Every response carries `capability_version` (the package's semantic version), `prompt_version`
(the prompt file's), `model` (the register alias and the concrete model id the adapter used) and
`eval_set_version` (the set the prompt was last measured against). The backend stores them with
the result; when quality drifts, the tuple says which change did it.

## 4. Degradation is designed, never improvised

Each descriptor names what the backend receives when the capability cannot run: an error from
the catalog with `retry_after` where retrying makes sense, never a fabricated or partial result
presented as whole. `ai.capability.disabled` (kill switch) and `ai.budget.exceeded` are
first-class outcomes with their own tests; the backend decides what the user sees.

## 5. The golden capability

The first capability built (`improve-story`) is the reference: every later capability copies its
package shape, its test layout and its eval set layout. A deviation from the golden shape is a
`Q-NNN` with the reason the shape does not fit (`RULE-007 §3`); the scaffolder `make new-capability`
produces the shape.

## 6. Streaming capabilities

A capability that streams (`assistant-chat`) runs stages 1–4 before the first frame, streams stage
5, and runs 6–7 on the accumulated completion before the terminal frame; a failure in 6 sends a
terminal error frame and the partial frames are discarded by the backend (`ARCH-004 §4`).
