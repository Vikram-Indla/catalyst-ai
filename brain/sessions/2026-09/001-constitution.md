# 001 — constitution

**Date:** 2026-09-18 · **Ticket:** AI-001 · **Capability or package:** none (documentation) · **Author:** a contributor

## Read
The backend's `ENGINEERING.md`, `docs/00-START-HERE.md`, `RULE-000`, `RULE-001`, `RULE-004`,
`RULE-005`, `RULE-006`, `RULE-007`, `RULE-008`, `ADR-000`, `ADR-003`, `ARCH-004 §7`, `ARCH-005`,
`ARCH-006 §1`, `ARCH-010`, `docs/04-ledgers/README.md` — the shape this repository mirrors. The
previous system's `supabase/functions/{ai-*,docintel-*,kb-*,caty-chat,chat-*,standup-*,
summarize-*,release-notes-generate,workflow-ai,folio-ai-search}` and `_shared/{llm,lovable-ai,
ai-cache,embed_stage,prompts}.ts` — read for behaviour only, for the capabilities ledger. A
sibling Python service's rule page and tool configuration (`ruff.toml`, `mypy.ini`,
`.importlinter`, `.coveragerc`, a gate runner) — reused where the reason holds, tightened where
it does not; each reuse is named in the page that carries it.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-001
Capability:      none — the law under which every capability is born
Inputs:          none
Tenant boundary: none touched; the boundary is defined (ARCH-002, ADR-002)
Provider/model:  none; the register is created empty of adapters (ADR-004)
Prompt version:  none
Eval set:        none; the policy is defined (ADR-005, RULE-008)
Budget:          none; the budget rule is defined (ARCH-008, RULE-004 §5)
Failure mode:    none; the error catalog's four families are defined (RULE-003 §2)
Cache:           none; the key rule is defined (ARCH-008 §3)
Safety:          none; the threat template and ARCH-009 are defined
Contract:        none; contract-first is defined (ARCH-004); the job model chosen (ADR-007)
Invariants:      INV-001..INV-030 created in this change
Blast radius:    SYSTEM — every future file is governed by these pages
Decision level:  3 — the constitution; adopted by the lead as D-001
ADR:             ADR-001..ADR-007
```

## Changed
- `ENGINEERING.md` — the bootstrap: precedence, session sequence, layout, the ten hard lines
- `README.md` — a pointer to `ENGINEERING.md`
- `docs/00-START-HERE.md` — the folder map, reading order, identifiers, how a decision travels
- `docs/01-architecture/ARCH-001..012` — overview, boundary and data classes, capabilities and the
  pipeline, the contract, providers and the port, retrieval and storage, evaluation, cost and
  budgets, security, observability, repository layout, dependency direction and fitness
- `docs/02-rules/RULE-000..009` — law, code quality, Python standards, contracts and errors,
  testing and evals, git and sessions, enforcement map, engineering protocol, prompts and eval
  sets, lifecycle
- `docs/03-adr/ADR-000..007` — template; Python and the stack; the boundary; dependency policy
  and register; providers and the first provider; evaluation; the service's own database; the job
  model
- `docs/04-ledgers/{README,capabilities,contracts-changelog,errors,config,providers,eval-sets,invariants}.md`
- `docs/05-threat-models/{README,THREAT-000-template}.md`, `docs/06-runbooks/README.md`,
  `docs/07-GLOSSARY.md`
- `brain/{01-STATUS,02-DECISIONS,03-FINDINGS,04-OPEN-QUESTIONS}.md`, `brain/sessions/_TEMPLATE-session.md`

## Verify
```
$ make verify
unavailable — no Makefile exists yet; the gate is built by AI-002 under RULE-006. This change is
documentation only; the lead's review is the gate for it (RULE-000 §1).
```
```
$ make ci
unavailable — same reason.
```

## Eval and budget numbers
No capability touched.

## Decisions and questions
- D-001 proposed: adopt `RULE-000..009`, `ARCH-001..012`, `ADR-001..007` as the constitution.
- D-002 proposed: adopt `ADR-007` (synchronous operations with idempotency keys; polled jobs for
  long ones; the service never calls the backend) — announced to the backend before adoption.
- Q-001: the display of people in digests and summaries — the previous system read names from
  the profiles table (RESTRICTED under `ARCH-002 §3`); the backend must send opaque labels or the
  product must accept that summaries name nobody. A product decision, not this repository's.
- Q-002: which capabilities may retain content for quality review (opt-in per organisation,
  `ARCH-010 §4`) — none until the lead says otherwise.
- F-001: the previous system's `chat-unfurl`, `kb-feedback`, `kb-cleanup`, `ai-theme-prewarm`
  contain no model call; they are backend or retention concerns, recorded in the capabilities
  ledger as "retired without a capability" pending the backend's confirmation.

## Commit
Files: `ENGINEERING.md`, `README.md`, `docs/**`, `brain/**`
Proposed: `docs: constitution — law, architecture, seven ADRs, ledgers, brain`
Green light: given by the lead on 2026-09-19 — committed on local `main` in the proposed order (no remote yet)

## Next
AI-002 — the scaffold under this law: `uv`, FastAPI health, the `Provider` port, `tools/checks`,
`.githooks`, `make verify`, `make ci`, the OpenAPI drift check.
