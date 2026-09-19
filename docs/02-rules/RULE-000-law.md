---
id: RULE-000
title: Law — precedence, scope, what gets work rejected
status: Binding
version: 1.0.0
owner: AI service lead
created: 2026-09-18
---

# RULE-000 — Law

Everything in `02-rules/` elaborates this page. Every rule here and below has a row in
`RULE-006-enforcement.md` naming the check that enforces it. A rule without a check is a defect
in the rule, not a licence to ignore it.

## §1 Precedence

1. The lead's explicit instruction, recorded as `D-NNN` in `brain/02-DECISIONS.md`.
2. These rules.
3. The ADRs in `docs/03-adr/`.
4. The architecture pages in `docs/01-architecture/`.
5. The code. Where code and documentation disagree, file `F-NNN`; never pick silently.

Conflicts at the same level stop the work and produce a `Q-NNN`. Where this repository's
documentation and the backend's disagree about the contract between them, the contract
changelog of this repository and an `F-NNN` settle it — never a silent edit on either side.

## §2 Scope discipline

- A ticket names a capability or a package. Work stays inside it and in the shared documentation.
- Something noticed outside the ticket is a finding or a question, not a fix.
- Blocked is recorded as blocked, with the reason. Nothing is quietly descoped.
- A ticket that turns out to need a second provider, a new retrieval index, a contract change,
  a new dependency, a new table, or a product decision, stops and asks before doing it.
- A product question — tone, language, what to hide, whose name may appear — is a `Q-NNN`,
  never a prompt edit.

## §3 Rejected on sight

- A red `make verify` or `make ci`, or a green one that was not pasted into the session record.
- A capability without an eval set; a prompt or pipeline change without the eval numbers pasted;
  a threshold lowered or a budget widened without a `D-NNN`.
- A prompt string in code; a prompt file without its header; a prompt edited in place after release.
- A test that opens a socket; a fixture re-recorded without a reason in the record.
- A model id outside the register and configuration; a provider reached outside the port.
- A `RESTRICTED` field in a request model; a request field without a data class; a log line, an
  error, a trace attribute, a metric label or a fixture carrying prompt or completion content.
- A query on a tenant table without `organization_id`; a tenant table without RLS; a cache key
  without the organisation.
- A file over 300 logical lines; a function over 50 lines; cyclomatic complexity over 10; more
  than 5 parameters; more than 10 branches; nesting over 3; a banned filename stem; a package
  holding two capabilities; a fixture outside `tests/fixtures/`.
- A comment that is not a docstring on a public surface, a module docstring, or a tool
  directive with its reason; a `noqa` or `type: ignore` without an allowlisted reason.
- A raw `dict`, `Any` or untyped JSON crossing a route, a pipeline surface or the port.
- `os.environ` outside `config/`; a global mutable; a notebook; `print`.
- Coverage under the layer floor (`RULE-004 §1`); a logic module without a test module.
- A dependency added without a register row (`ADR-003 §3`); a licence outside the allowlist; a
  secret anywhere in the tree; a vulnerability above the allowed severity.
- A contract change without a changelog entry and the "backend must" line; a breaking change
  without a version.
- A commit made from a working session without the explicit green light in chat (`RULE-005`).

## §4 Honesty primitives

"Green" means `make verify` printed it and `make ci` printed it. "Done" means the ticket's
acceptance evidence exists and is pasted, including the eval score and the p95s when a capability
was touched. "Blocked" names the blocker. "Unavailable" is the word for data that does not exist —
never a fabricated value, never "the model usually gets it right".

## §5 Definition of done

A change is done when: `make verify` and `make ci` are green with zero warnings · tests shipped
in the same change (a bug fix starts with the failing regression test; a quality regression starts
with the failing eval case) · error, empty, boundary, injection and leakage cases are tested · the
contract, the ledgers and the changelog moved with the code · the eval set is versioned and the
thresholds are met with the numbers pasted · the budgets are met with the numbers pasted · the
degradation is defined and tested · observability exists for the capability (a dashboard row and
the alert at 80% of budget) · the runbook line exists · the session record has the evidence · the
brain is updated if a decision was made · the change is deployable alone.

## §6 The constitution — what cannot change implicitly

The following change only through an ADR, explicit lead approval recorded as a `D-NNN`, a
migration plan, and test evidence — never through a ticket, a refactor, or a contributor's judgement:

1. The boundary: one caller, no product table, no business rule (`ADR-002`)
2. Data classification at the door and the `RESTRICTED` refusal (`ARCH-002 §3`)
3. Tenancy of the service's own storage (`ADR-006`)
4. Dependency direction between layers and the independence of capabilities (`ARCH-012`)
5. The contract compatibility policy (`ARCH-004 §6`)
6. The provider port and the retention rule (`ADR-004`, `ARCH-002 §4`)
7. The evaluation policy — sets before prompts, thresholds as floors (`ADR-005`)
8. The job model and the direction of calls (`ADR-007`)
9. The security baseline (`ARCH-009`)
10. Observability without content (`ARCH-010`)

Every item is a row in `docs/04-ledgers/invariants.md` with an executable form in
`tests/architecture/` (`ARCH-012 §4`). A red test there is reported as `ARCHITECTURE VIOLATION`
and is never fixed by editing the test.

## §7 Decision levels

| Level | Examples | Recorded where |
| --- | --- | --- |
| 0 — implementation | Rename, extract, a post-processing tweak, a new unit test, a new eval case | Nowhere beyond the diff |
| 1 — local design | A new stage helper inside a capability, a new grader, a new fixture, a prompt version | The ticket and the session record (with the eval numbers) |
| 2 — architectural | A new capability, a contract operation or field, a new model alias, a new corpus, a new platform package, a new dependency | An ADR (`Proposed` → `Accepted`) or the capability's descriptor reviewed in the change |
| 3 — irreversible | Anything in §6; a second provider; a threshold lowered; a budget widened; content retention; deletion semantics | An ADR **and** a `D-NNN` from the lead, with migration plan and evidence |

A session unsure of the level treats it as one higher and asks.
