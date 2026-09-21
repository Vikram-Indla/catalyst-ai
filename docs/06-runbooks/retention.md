# Retention — the retention job, organisation deletion, the zero-rows proof

## The database roles

The migration creates two roles the application assumes with `SET ROLE`: `catalyst_ai_app`
(every connection of the pool; bound by the `tenant_isolation` policy that reads `app.org_id`)
and `catalyst_ai_maintenance` (assumed only inside the jobs, for the cross-organisation listing).
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
