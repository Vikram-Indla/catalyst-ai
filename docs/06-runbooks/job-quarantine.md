# `JobQuarantined` — a job row failed its stored proof

Something presented work to the service that the backend did not sign for it, through the table
instead of the door.

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

## A rise in refused requests

The door's refusals are `OriginRefusalsHigh` and `OriginForged`, and their page is
`origin-refusals.md`. A quarantine and a forged request in the same hour are one incident:
start from `bad_signature` there.
