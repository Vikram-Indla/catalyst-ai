---
id: ARCH-009
title: Security — injection, leakage, abuse, secrets
status: Locked
version: 1.0.0
owner: AI service lead
created: 2026-09-18
---

# ARCH-009 — Security

The model is an untrusted input generator, and everything a user typed is untrusted data. The
baseline: OWASP ASVS 5.0 for the service and the OWASP LLM top ten for the pipeline; every
capability family has a threat model (`docs/05-threat-models/`) before production.

## 1. Trust boundaries

| Boundary | Where trust changes |
| --- | --- |
| Service token | middleware verifies `Authorization: Bearer` against configuration (constant-time compare); `401` before any route; rotation supports two active tokens |
| Tenant | `organization_id` from the validated request; set on the storage session before any query; never from a header alone |
| Input | every user-supplied text is `CONFIDENTIAL` data; it is delimited and role-separated in assembly and is never an instruction (`RULE-008 §2`) |
| Provider | the completion is untrusted: parsed against the schema, scanned for leakage, never executed, never rendered as markup by this service |
| Storage | RLS on every tenant table; the application role cannot bypass it |

## 2. Injection is an input problem

- Every user segment is delimited with a stable marker and introduced as data in the developer
  segment; the output schema cannot carry a command (no free-text "action" fields).
- The input scanner (`platform/safety/input.py`) refuses values that match credential and secret
  patterns, exceed size limits, or contain control sequences — `ai.input.rejected` with a reason
  class, logged as a security event without the value.
- Each capability's test suite carries injection cases: instructions embedded in a title, a
  comment that asks the model to reveal its prompt, a document with hidden text. The eval set's
  `injection` tag is required to be non-empty (`tools/checks/evals`).

## 3. Leakage is an output problem

- The output scanner (`platform/safety/output.py`) refuses completions containing another
  organisation's identifiers (a key pattern the request did not carry), secret patterns, URLs
  the request did not contain, or instructions to the user to act outside the product —
  `ai.output.invalid`, logged as a security event, never returned.
- Retrieval never crosses a tenant (`ARCH-006 §3`); grounded answers cite only chunks the tenant
  owns; a citation outside the retrieved set is `ai.output.invalid`.

## 4. Abuse

Per-tenant and per-capability budgets in the service (`ARCH-008 §2`); request size limits per
field in the contract; a per-organisation concurrency cap; the kill switch per capability in
configuration (`RULE-009 §2`). A tenant that exhausts a budget receives `ai.budget.exceeded`,
never a degraded answer.

## 5. Secrets

Provider keys, the service token and the database URL come only from the runtime environment
through the settings object (`RULE-003 §5`); `gitleaks` runs in `make verify-fast`; `pip-audit`
in `make security`; the image is scanned. A key never appears in a log, an error, a trace or a
fixture; recorded fixtures are scrubbed on capture (`ARCH-005 §3`).

## 6. Documents

`ARCH-006 §4`: size and time limits, no macros, no external fetches, killable subprocess,
failure as `ai.input.rejected`.
