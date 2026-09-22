# Runbooks

One page per failure domain, written with the feature that needs it. Every capability adds its
line to the capability runbook; a `built` capability without one is a finding (`ARCH-010 §5`).

| Page | Domain | Lands with |
| --- | --- | --- |
| `provider-outage.md` | breaker open, timeouts, quota; what the backend receives; the fault-injection rehearsal | the first adapter |
| `eval-drift.md` | a score falls below a floor after a provider model change; how to re-record, re-run, decide | the first capability |
| `budget-exhaustion.md` | a tenant hits its cap; how to read the counters, raise an override, find the runaway | the budgets package |
| `kill-switch.md` | disabling a capability without a deploy; what each capability degrades to | the first capability |
| `index-rebuild.md` | re-embedding a corpus after a model or chunking change; convergence by the retrieval eval | `work_items` (present) |
| `job-backlog.md` | queue age, stuck jobs, expiry; the per-organisation concurrency dial; drain | the worker (present) |
| `retention.md` | the retention job, organisation deletion, the zero-rows proof, the database roles | the storage package (present) |
| `key-rotation.md` | rotating the backend's signing key with two public keys active; the emergency sequence; what to watch | the origin middleware (present) |
| `job-quarantine.md` | a job row that failed its proof; a rise in refused origins — reasons, the first three commands, when to page | the origin middleware (present); the worker when the table lands |
| `capabilities.md` | one line per capability: what to check when quality drops, the switch, what the backend shows | `improve-story` (present) |
| `origin-refusals.md` | the door is turning callers away: the reason table, what each one means, when to page | the origin middleware (present) |
| `replay-store-down.md` | the replay store cannot answer and the door fails closed; every capability is down | the origin middleware (present) |
