# Contracts changelog

Every change to anything the backend relies on (`RULE-003`): an operation, a request or response
shape, an error code, a header, a stream frame, a job status, a configuration variable, a port
method. Newest first. Written by hand in the same change as the contract; `tools/checks/changelog`
fails a change to `api/openapi.yaml` without an entry here.

Entry template:

```
## YYYY-MM-DD · AI-NNN · <capability or platform>
**Kind:** ADD | CHANGE | DEPRECATE | REMOVE | FIX
**What:** <operationId(s) / error code(s) / header(s) / setting(s)>
**Backend must:** <action or "nothing">
**Sunset:** <date, for DEPRECATE>
```

---


## 2026-09-18 · AI-003 · improve-story
**Kind:** ADD
**What:** `improve_story.run` (`POST /v1/improve-story`), request `ImproveStoryRequest` (every field
classified; `mode`, `item_type`, `title`, `description`, optional `acceptance_criteria`,
`focus_hint`, `parent_title`, `parent_description`, `language`), response `ImproveStoryResponse`
(the envelope plus `improved_description`, `acceptance_criteria`, `rationale`, `changed`,
`confidence`); error codes `ai.contract.version_mismatch`, `ai.capability.disabled`,
`ai.input.rejected`, `ai.input.too_large`, `ai.budget.exceeded`, `ai.provider.unavailable`,
`ai.provider.timeout`, `ai.provider.rejected`, `ai.provider.quota`, `ai.output.invalid`,
`ai.output.unsafe`; header `Idempotency-Key` honoured; settings `PROVIDER_GEMINI_API_KEY`,
`PROVIDER_GEMINI_BASE_URL`, `MODEL_TEXT_DEFAULT`, `CAPABILITY_IMPROVE_STORY__*`.
**Backend must:** send `organization_id` and `capability_version: "1.0.0"` in every body; send no
`RESTRICTED` value (names, emails, IPs, secrets) in any text field — the door refuses with
`ai.input.rejected` and a reason class; send `Idempotency-Key` derived from its own command id on
retries; read `capability_version`, `prompt_version` and `model` from the response and store
them with the proposal; treat `ai.capability.disabled` and `ai.budget.exceeded` as
first-class outcomes (no retry on the first; `Retry-After` on the second); never show the
`rationale` as a stored fact — it is the proposal's explanation.

## 2026-09-18 · AI-004 · generate-children
**Kind:** ADD
**What:** `generate_children.run` (`POST /v1/generate-children`), request `GenerateChildrenRequest`
(every field classified; `target` — `stories` | `epics` | `children`; `hierarchy[]` the organisation's
ordered levels top first; `parent_level`; optional `child_level` — must be the level under the parent;
`parent_title`, `parent_description`, `source_texts[]`, `siblings[] {key?, title}`, `focus_hint?`,
`max_items` 1–20, `language?`), response `GenerateChildrenResponse` (the envelope plus `candidates[]
{type, title, description, acceptance_criteria[], confidence, duplicate_of?}`, `empty_reason?`,
`confidence?`); error codes as `improve_story.run`, with `ai.output.invalid` carrying the detail
`hierarchy_violation` when a candidate is not at the child level and `ai.input.rejected` carrying it
when the request names a child level that is not the parent's next; settings
`CAPABILITY_GENERATE_CHILDREN__*`.
**Backend must:** send the organisation's hierarchy as data on every call (the service knows no
registry) and validate every candidate's `type` against the organisation's enabled types again before
creating anything — the service knows the list it was sent, not the tenant's enablement; treat
`candidates[]` as proposals and own creation, ordering and ranking; skip or merge candidates whose
`duplicate_of` names a sibling; show `empty_reason` when the list is empty rather than retrying;
send extracted attachment text in `source_texts[]` when the product wants attachments considered
(never URLs); apply the same `Idempotency-Key`, `capability_version` and `RESTRICTED` rules as for
`improve_story.run`.
