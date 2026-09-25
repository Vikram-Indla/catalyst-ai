# Glossary

One word per concept; the vocabulary the code, the docs, the contract and the backend share.
Changed through a `D-NNN`. Where the backend's glossary defines a product word (work item,
organisation, project), this service uses that word and never a synonym.

| Word | Means here | Never |
| --- | --- | --- |
| **capability** | one thing the service does, as one package, one operation, one eval set, one budget (`ARCH-003`) | feature, skill, tool, plugin |
| **feature** | what the product does with a capability; owned by the backend and the apps | — |
| **the backend** | the Go service that is this service's only caller | the client, the API |
| **contract** | `api/openapi.yaml`, rendered from the models in `contract/` | the spec (that is the backend's word for its own) |
| **descriptor** | the capability's declaration: name, version, budget, prompt version, eval set version, data classes, kill-switch key | manifest, config |
| **pipeline** | the seven stages around one model call (`ARCH-003 §2`) | chain, flow, graph |
| **stage** | one of parse, validate, retrieve, assemble, call, validate output, post-process | step, node |
| **prompt** | a versioned file with a header; one per capability version | template, instruction string |
| **segment** | a named part of the port request: system, developer, user | message (that is the provider's word) |
| **port** | the `Provider` protocol; the only way to a model | client, gateway, wrapper |
| **adapter** | one provider's implementation of the port | driver, plugin, integration |
| **provider** | a company's model API behind an adapter | vendor, LLM |
| **model alias** | the name a capability uses (`text-default`); the register resolves it | model name, model id (that is the concrete one) |
| **register** | `docs/04-ledgers/providers.md` and `docs/03-adr/ADR-003 §3`: models and dependencies with reasons | list, catalog |
| **fixture** | a recorded provider response replayed in tests | mock, stub, cassette |
| **recording** | the human action that captures a fixture with a real key | — |
| **eval set** | cases, graders, thresholds and a README, versioned, beside the capability | test set, benchmark, golden set |
| **grader** | a function scoring one property of a response in `[0, 1]` | judge, metric |
| **threshold** | a floor a grader's aggregate must clear; lowered only by decision | target, goal |
| **budget** | the declared p95 latency and p95 cost per call; a test | limit, quota (the tenant's cap is a *cap*) |
| **cap** | the per-organisation spend and concurrency limits enforced in stage 2 | budget |
| **data class** | `PUBLIC` · `INTERNAL` · `CONFIDENTIAL` · `RESTRICTED`, per field, from the backend's classification | sensitivity, PII flag |
| **the door** | stage 2: where data classes, size, the scanner, the switch and the cap are enforced | guard, middleware |
| **scanner** | `platform/safety`: the input scanner (secrets, control sequences) and the output scanner (foreign ids, secrets, URLs) | filter, moderation |
| **degradation** | the documented error the backend receives when a capability cannot run | fallback (implies a substitute answer — there is none) |
| **kill switch** | `CAPABILITY_<NAME>__ENABLED=false` | feature flag |
| **job** | a long capability run the backend polls (`ADR-007`) | task, background process |
| **the job line** | 20 s: synchronous below, a job above | — |
| **corpus** | a named set of things the service embeds for one tenant (`work_items`, `pages`, `documents`, `knowledge`) | index (that is the physical structure), collection |
| **chunk** | one embedded unit with provenance | passage, document (that is the source) |
| **provenance** | the chunk, key or page a claim or match rests on; returned with the result | citation (the assistant's frame name), source |
| **groundedness** | every claim in an answer is supported by a provenance entry | faithfulness, hallucination rate |
| **confidence** | a deterministic grader's score returned with a result; `null` when no grader exists | probability, certainty |
| **participant label** | the opaque name the backend gives a person in a request | name, user, author |
| **the gate** | `make verify`; identical to CI; `make ci` runs it in the image | the checks, the pipeline (that is CI's run) |
| **plant** | a deliberately violating file under `tools/checks/selftest/plants/` that proves a check red | fixture |
| **the golden capability** | `improve-story`, the shape every capability copies | reference implementation, example |
| **record** (session) | `brain/sessions/<YYYY-MM>/NNN-<slug>.md` | log, notes |
| **the lead** | the person who commits, decides, and answers `Q-NNN` | owner, maintainer |
| **a contributor** | anyone or any tool working in a session under `RULE-007` | — |
