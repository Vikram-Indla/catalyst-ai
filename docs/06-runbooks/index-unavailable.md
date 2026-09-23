# `IndexUnavailable` — the retrieval index is not answering

Page severity. The index is the service's own PostgreSQL with `pgvector` (`ARCH-006`). When a
read or a write to it fails, the operation answers `503 ai.index.unavailable`, asks for a retry
after five seconds, and says nothing more.

## What stops, and what keeps answering

Stops: `search.run`, `index.upsert`, `index.delete`, `documents.ingest`, `documents.ask`,
`documents.generate`, and the assistant's reads of a space. Keeps answering: every capability
that does not retrieve (`improve-story`, `translate`, `summarize`, …); `generate-children`
answers without its de-duplication pass over the index. The backend re-sends upserts it was
refused; nothing indexed before the outage is lost.

## The first three commands

1. `/readyz` on the ops port: `checks.storage` false means the pool cannot reach the database
   at all; true with the alert firing means the database answers but the index statements fail
   (a missing extension, a migration not run, a role without its grant).
2. `sum(rate(catalyst_ai_errors_total{code="auth.origin.unverifiable"}[15m]))` — the replay
   store lives in the same database. Both alerts firing is the database itself:
   `replay-store-down.md` owns it, because the door is failing closed for every capability.
3. The process's start-up log: `storage unavailable at startup` means the pool was never
   opened, and every index call fails until the process is restarted (it does not exit by
   itself yet). Without that line, it is the database or the network between.

## What to do

- **The database is down or unreachable:** restore it; the pool picks the connections up again
  on the next checkout. A process that logged `storage unavailable at startup` needs a restart.
- **The statements fail:** `catalyst-ai migrate` against the database, then check the
  application role's grants (`retention.md`, the database roles).
- **Prolonged, and generation is healthy:** `CATALYST_AI_CAPABILITY_SEARCH__ENABLED=false`
  turns the refusals into `ai.capability.disabled`, which the backend shows as unavailable
  rather than as a failure (`kill-switch.md`).

## What never helps

A rebuild. `index-rebuild.md` re-embeds a corpus after a model or chunking change; against an
index that is not answering it only adds load, and it moves no row until the database answers.
