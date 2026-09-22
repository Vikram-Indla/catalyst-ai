# Quarantine — a job row that failed its proof, and a rise in refused origins

Two alerts share this page because they share a cause: something presented work to the service
that the backend did not sign for it.

## `job_quarantined` (the worker refused to run a row)

A job row is never trusted for being in the table. Before executing, the worker verifies the
envelope the row carries — signature, issuer, audience, the organisation and capability the row
names, the hash of the payload bytes it is about to run, and the job window — and moves a
failing row to `quarantined` with the reason (`catalyst-ai worker`, `platform/jobs`).

**What it means.** By reason:

| Reason | Most likely cause | Do |
| --- | --- | --- |
| `malformed` | a row inserted by hand or by a tool, not through the API | treat as an intrusion until shown otherwise: who has write access to the service's database? |
| `organization_mismatch`, `capability_mismatch` | an envelope copied from one row onto another | the same |
| `body_mismatch` | the payload edited after the API stored the row | the same |
| `unknown_key` | a rotation removed the key before the longest job window closed | list the old key again for the window, then remove it (`key-rotation.md` step 4) |
| `bad_signature` | a forged envelope under a known key id | intrusion; rotate the key (`key-rotation.md`, emergency) |
| `no_job_window` | the backend enqueued a job without `job_exp` | a backend defect against the changelog entry; the backend resubmits with the window |
| `job_expired` | the queue held the row longer than the capability's window | the backend resubmits; look at `job-backlog.md` for why the queue is slow |

**First three commands.**

1. Count by reason over the last hour (the counter `job_quarantined{reason}` on the metrics
   endpoint; the security log line `job_quarantined` carries the job id and the reason).
2. Read the quarantined rows' ids, organisation, capability and `created_at` — never the
   payload — and check the audit of who wrote to the database in that window.
3. If the reason is anything but `unknown_key`, `no_job_window` or `job_expired`: page, and
   start the emergency rotation.

A quarantined row is never re-queued by the service; the backend resubmits under a fresh
envelope once the cause is known. Rows are kept for the audit and expire with the job result TTL.

## `origin_refused` (the door refused N requests in a window)

Every refused request is one security event with a reason and one increment of
`origin_refused{reason}`; the caller sees `401 auth.origin.invalid` and nothing else.

| Reason | Most likely cause | Do |
| --- | --- | --- |
| `missing`, `malformed` | something that is not the backend is calling: a scanner, an old client with a bearer | find the source address in the ingress log; the service is unaffected |
| `unknown_key` | a rotation out of order | `key-rotation.md` |
| `bad_signature` | a forged envelope or a corrupted one | intrusion until shown otherwise; rotate |
| `expired`, `not_yet_valid`, `too_long_lived` | clock drift on one side, or the backend signing at enqueue time instead of send time | compare the two clocks; the tolerance is `AUTH_CLOCK_SKEW_SECONDS` |
| `replayed` | a retry that re-sent the same envelope (a backend defect), or a real replay | the backend must sign every attempt afresh; if it does, treat as an attack |
| `body_mismatch` | a proxy that rewrites bodies, or the backend hashing a different serialisation than it sends | compare the bytes; `bh` is over the bytes exactly as sent |
| `organization_mismatch`, `capability_mismatch` | the backend signed for one thing and sent another | a backend defect; its own log by request id |
| `unverifiable` | the replay store did not answer | the database: `ready`, the pool, `retention.md`'s roles; the backend retries after `Retry-After` |

**When to page.** Any `bad_signature`; `replayed` or `body_mismatch` that the backend cannot
explain within the hour; a sustained rate of any reason from a source that is not the backend.

**When to disable a capability.** Never for this alert — the door is before every capability
and refusing is the correct behaviour. The kill switch is for a capability that misbehaves after
the door.
