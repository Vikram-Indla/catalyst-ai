# Retention — the retention job, organisation deletion, the zero-rows proof

## The database roles

The migration creates two roles the application assumes with `SET ROLE`: `catalyst_ai_app`
(every connection of the pool; bound by the `tenant_isolation` policy that reads `app.org_id`)
and `catalyst_ai_maintenance` (assumed only inside the jobs, for the cross-organisation listing).
Three logins hold them (`db/provision/logins.sql`, run once by the provisioner; passwords or the
platform's identity binding are set out of band): `catalyst_ai_serve` (`DATABASE_URL`) is a member
of the application role only, so the process that answers requests can neither read another
organisation nor migrate; `catalyst_ai_worker` (`DATABASE_WORKER_URL`) adds the maintenance role
for the claim, the purge and the index jobs; the owner (`DATABASE_MIGRATE_URL`) is used by
`catalyst-ai migrate` alone. Staging and production refuse to start unless the three are set and
name three different users. The storage suite proves serve's `SET ROLE catalyst_ai_maintenance` is
refused (`INV-073`). The queue gauges are read on the worker's ops port only.
Row level security is forced on every tenant table, so the owner is bound too. **The login user
of `DATABASE_URL` must not be a superuser in staging or production** — a superuser bypasses RLS
by definition; the compose file's local user is one, which is why the storage suite proves
isolation with `SET ROLE catalyst_ai_app` and a raw query rather than trusting the login.

## The retention job

`catalyst-ai retention` forgets, per organisation, every indexed document the backend has not sent
for `RETRIEVAL_DOCUMENT_TTL_DAYS` (default 400): `last_seen_at` is stamped by every `index.upsert`
that touches the document, changed or not. Run it daily; it is idempotent and reports the
organisations visited and the documents removed. A document the backend still has is re-indexed
on its next upsert.

## Organisation deletion

The backend calls `index.delete` with every key it holds for the organisation; what it no longer
knows about falls to the retention job. When the jobs table lands, one call will do it.

## The zero-rows proof

`tests/storage/test_postgres.py` opens a raw connection, assumes `catalyst_ai_app`, sets one
organisation and selects without a `WHERE`: only that organisation's rows come back, a write for
another organisation is refused, and with no organisation set nothing comes back. Run `make
storage` to reproduce it against a throwaway container.

## The replay store's cleanup

`auth_nonces` forgets its expired rows in the same transaction as every accepted request
(`nonce_forget` before `nonce_remember`), so the table holds at most the envelopes of the last
`AUTH_MAX_TTL_SECONDS` (60 s by default). It needs no job and no schedule: the cadence is every
request.

## Backups and deletion

The database's backup class is point-in-time recovery for **7 days** plus a daily backup kept
for **14 days** (the lead's decision). A document or an organisation deleted here is gone from the
live database at once and from every backup **14 days** later; the product's deletion promise
names the same 14 days. The window is the platform's setting, recorded in the infrastructure
ledger; when it changes, this paragraph and the product's promise change with it. The backups
mostly guard the two tables a rebuild cannot bring back (`index-rebuild.md`); every index
converges without them.
