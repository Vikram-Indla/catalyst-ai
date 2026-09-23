# `OriginUnverifiable` — the replay store cannot answer, and the door is failing closed

**Alert:** `OriginUnverifiable` (page).

## What it means

The door honours a request's nonce exactly once, and the nonces live in `auth_nonces` in the
service's own database. When that table cannot be read or written, the door cannot know whether a
request is a replay — so it **refuses**: `503 auth.origin.unverifiable` with `Retry-After`, and
the backend retries. Nothing is served on a maybe. Every capability is down for as long as this
lasts; that is why it pages.

## The first three commands

1. `/readyz` on the ops port: `storage: false` confirms the database, not the door. If storage is
   `true` and this alert is firing, the failure is in the nonce table alone — a lock, a full
   disk, or a permission that moved (see 3).
2. `sum(rate(catalyst_ai_errors_total{code="auth.origin.unverifiable"}[5m]))` beside
   `sum(rate(catalyst_ai_errors_total{code="ai.index.unavailable"}[5m]))` — both rising together
   is the whole database; only this one is the table or its grants.
3. Against the database, as the application role:
   `SELECT count(*) FROM auth_nonces;` — a refusal here names the cause (connection, permission,
   relation). `GRANT SELECT, INSERT, DELETE ON auth_nonces TO catalyst_ai_app, catalyst_ai_maintenance;`
   is what the migration gave it; `retention.md` describes the two roles.

## What to do

- **The database is down**: this is a database incident; the door's behaviour is correct and
  nothing here needs changing. The backend's retries will drain the moment it answers.
- **The table is missing or ungranted** (after a restore, a new environment, a hand-edited
  role): run `catalyst-ai migrate`, then re-check the grants. A new environment that never ran
  the migration shows exactly this.
- **The table is enormous**: expired rows are deleted on each insert, so growth means inserts are
  failing rather than succeeding — see the first bullet, or look for a long transaction holding
  the table.

## What never helps

Disabling the door, or serving requests while the store is unreadable. A nonce that is not
checked is a replay that is not caught; the refusal is the design, and the fix is the database.

## When to page

Immediately, and it is already a page: this is total unavailability of every capability. If it
clears on its own within the retry window, keep the ticket — an intermittent replay store is a
database problem that will return at a worse hour.
