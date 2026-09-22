---
id: ARCH-009
title: Security — injection, leakage, abuse, secrets
status: Locked
version: 1.1.0
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
| Origin | the backend signs every request (Ed25519, its private key only in its own runtime); the service holds the public keys by `kid` (two during a rotation) and verifies before any route: signature, issuer, audience, a window of at most 60 s with a bounded clock skew, a nonce honoured once (the replay store), the body hash, and the organisation and capability the request itself names; a failure is `401` without detail, logged as a security event with its reason and counted; the service holds no signing key and no static token (`tools/checks/origin`, `D-035`) |
| Job | a job row is never trusted for being in the table: it carries the envelope the API verified and the hash of its payload, and the worker verifies both again before executing under the job's own window (`job_exp`); a row that fails is `quarantined` with the reason, never run (`D-036`) |
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

Provider keys, the backend's public keys and the database URL come only from the runtime environment
through the settings object (`RULE-003 §5`); `gitleaks` runs in `make verify-fast`; `pip-audit`
in `make security`; the image is scanned. A key never appears in a log, an error, a trace or a
fixture; recorded fixtures are scrubbed on capture (`ARCH-005 §3`). The service holds no
private key and no shared secret with the backend: a leak on this side forges nothing
(`tools/checks/origin` refuses a signing primitive, a stray cryptography import or a bearer
in the tree). Key rotation is `docs/06-runbooks/key-rotation.md`.

## 6. Documents

`ARCH-006 §4`: size and time limits, no macros, no external fetches, killable subprocess,
failure as `ai.input.rejected`.
