# NNN — <slug>

**Date:** YYYY-MM-DD · **Ticket:** AI-NNN · **Capability or package:** <name> · **Author:** <who>

## Read
The rule and architecture pages the ticket names; the files changed; the behaviour reference
(the previous system's function) if the ticket retires one. Nothing else.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-NNN
Capability:      <name or "none">                       (ARCH-003)
Inputs:          <field · data class> …                 (ARCH-002 §3)
Tenant boundary: <organization_id scope · storage rows touched>
Provider/model:  <provider · model alias from the register> (ARCH-005)
Prompt version:  <prompt_vN or "none">                  (RULE-008)
Eval set:        <evals/<name> vN · thresholds>         (ARCH-007)
Budget:          <p95 latency · p95 cost>               (ARCH-008)
Failure mode:    <error codes · degradation>            (RULE-003 §2)
Cache:           <key · TTL or "none">                  (ARCH-008 §3)
Safety:          <injection · leakage · abuse cases>    (ARCH-009)
Contract:        <operationIds added/changed · breaking?> (ARCH-004)
Invariants:      INV-NNN, …                             (docs/04-ledgers/invariants.md)
Blast radius:    LOCAL / CAPABILITY / CONTRACT / PLATFORM / SYSTEM
Decision level:  0 / 1 / 2 / 3                          (RULE-000 §7)
ADR:             none / ADR-NNN
```

## Changed
- `path/to/file.py` — one line on what changed and why the ticket needed it

## Verify
```
$ make verify
<pasted output, verbatim>
```
```
$ make ci
<pasted output, verbatim>
```

## Eval and budget numbers
Score per grader, p95 latency, p95 cost on the named set — or "no capability touched".

## Decisions and questions
- D-NNN filed / Q-NNN asked / F-NNN found (or "none")

## Commit
Files: <plain list>
Proposed: `type(scope): summary`
Green light: yes at HH:MM / no / not requested

## Next
The single next action for this ticket.
