# 031 — three logins, and a database a real environment can hold

**Date:** 2026-09-24 · **Ticket:** AI-023 · **Capability or package:** config (settings, logins), cli, app, platform/storage (migrate), platform/observability (scrape), `db/provision/`, the compose file, the storage suite, tools/evalkit, docs · **Author:** a contributor

The infrastructure review kept the design and named two things a real environment would break.
Every process logged in with one `DATABASE_URL` and could `SET ROLE` into either role, so the
request-facing process held a credential that could read every organisation, and could migrate.
And the first migration created `vector`, which a managed database's owner cannot do. Five lines
of the service's own docs were also owed.

## Read
The review; `ADR-006`, `ARCH-002 §3`, `ARCH-006 §1`, `ARCH-009 §5`; `runbooks/retention.md`,
`index-rebuild.md`, `replay-store-down.md`, `slos.md`; the migrations, `jobs_postgres.py`,
`postgres.py`, `migrate.py`, `cli.py`, `app.py`, the scrape, the storage suite.

## Impact matrix (RULE-007 §1, before any edit)
```
Ticket:          AI-023
Capability:      none
Inputs:          none
Tenant boundary: tightened — serve can no longer become the cross-organisation role
Provider/model:  unchanged
Prompt version:  unchanged
Eval set:        unchanged
Budget:          unchanged
Failure mode:    a deployment with one login refuses to start; a database without vector refuses
                 to migrate, naming the provisioning file; serve's scrape no longer shows the queue
Cache:           unchanged
Safety:          the least privilege per process
Contract:        no operation changes; two settings added (changelog)
Invariants:      INV-073 (new)
Blast radius:    PLATFORM — every process's database connection
Decision level:  2
ADR:             none (D-052; ADR-006 gains a revisit trigger)
```

## What changed
- **Three logins.** `DATABASE_URL` is serve's login, `DATABASE_WORKER_URL` is the worker's and the
  index jobs', and `DATABASE_MIGRATE_URL` is the owner's, for `catalyst-ai migrate` alone.
  `config/logins.py` refuses, outside development, a missing worker or owner URL and any two that
  share a user. `cli.py` gives each process its own login; development may run all three as one.
  `db/provision/logins.sql` is what the provisioner runs: `catalyst_ai_serve` (application role
  only) and `catalyst_ai_worker` (application and maintenance), both `NOINHERIT`, passwords set
  out of band.
- **The queue gauges** need the maintenance role, so only the worker's ops port reads them.
  Serve's `/metrics` shows its own counters.
- **`vector` required, never created.** `migrate` checks the installed version before any file:
  missing → "the vector extension is not installed; the provisioner creates it
  (db/provision/extensions.sql)…"; older than 0.5.0 (HNSW) → refused. The first migration's
  `CREATE EXTENSION IF NOT EXISTS` stays (forward-only) and is now a no-op. The suite's, the
  evals' and compose's throwaway databases run `db/provision/extensions.sql` first, as a
  provisioner would.
- **The version.** The development image carried pgvector 0.8.6 (read from `pg_extension`). The
  managed tier offers **0.8.1**, so every database the gate and compose start moves to
  `pgvector/pgvector:0.8.1-pg17` by digest (`sha256:3e8b3adf…`, read twice from the registry's
  manifest and compared): compose, the `make ci` sidecar and the hosted service, one string in
  `tools/rules.py` that the checks already hold equal. The storage suite asserts the database under
  test reports exactly `0.8.1`, so a silent tag move is red. The pre-flight floor stays 0.5.0. When
  the real instance exists, its `pg_available_extensions` decides, and the pin follows it.
- **The five lines.** `slos.md`: the database is on every request's path, so no objective beats
  its tier. `retention.md`: the three logins, the replay store's cleanup (every accepted request
  forgets the expired nonces in its own transaction, so the table holds at most a minute of
  envelopes), and backups and deletion (daily snapshot plus point-in-time recovery; a deletion
  leaves every backup when the platform's declared window passes, and the product's promise names
  the same window). `index-rebuild.md`: the number (500 000 chunks ≈ 137.5 M tokens ≈ US$ 21 at the
  register's price; 5 000 calls, about 70 minutes at the search budget, up to 14 hours at the
  deadline), and the two tables a rebuild does not bring back (`provider_calls`,
  `tenant_budgets`). `ARCH-006 §1` lists `index_documents_<corpus>` and the chunks' text as
  `CONFIDENTIAL`, and `ARCH-002 §3` says so.
- `ADR-006` revisit trigger, `D-052`, `INV-073`, the config ledger, the changelog.

## Every path that starts the service (the delivery review)
- **Compose stays one command.** The database mounts `db/provision/extensions.sql`, `logins.sql`
  and `development.sql` (the logins' local passwords, compose only) into its first-start scripts;
  `migrate` runs as the owner, `ai` as serve, and a new `worker` service as the worker. Proved on the
  pinned image with the three scripts mounted: all three ran; `migrate` as the owner applied 4;
  serve's `SET ROLE catalyst_ai_app` ok and `catalyst_ai_maintenance` refused; the worker's
  maintenance ok. `test_compose` holds the three users distinct and the three scripts mounted.
- **The gate provisions the same way on both sides.** The storage suite's own fixtures run
  `db/provision/extensions.sql` (and, for the login tests, `logins.sql`) through
  `tools/evalkit.provision` before migrating. They are reached by `make storage` and `make ci`,
  here and on the hosted runner alike; no workflow line provisions anything.
- **A rebuild is never a release step** (`index-rebuild.md`): the release deploys, the old index
  keeps serving, and the re-embed runs afterwards as its own operator-started job.

## Development passwords, and the backups (the reviews, then the lead)
- `db/provision/development.sql` commits the local logins' passwords, each its role's own name. The
  settings now refuse, outside development, any `DATABASE_*_URL` whose password equals its user
  name: one red test per URL, and a test that the compose file's three logins are all of that shape.
  gitleaks over `db/provision/` finds nothing (`INF no leaks found`), so no allow was added.
- `retention.md` states the lead's backup decision: 7 days of point-in-time recovery plus daily
  backups kept 14 days, so a deletion leaves every backup 14 days later.

## Red first
```
serve granted maintenance (the one-login status quo, planted in logins.sql)
  test_serve_cannot_become_maintenance_and_the_worker_can          FAILED  DID NOT RAISE InsufficientPrivilegeError
  test_serve_reads_its_tenant_but_never_counts_every_organisation  FAILED  DID NOT RAISE StorageUnavailableError
the pre-flight removed from migrate
  test_a_database_without_vector_is_refused_before_any_migration   FAILED  DID NOT RAISE ExtensionMissingError
restored: tests/storage 11 passed (against the pinned image on 127.0.0.1)
on pgvector 0.8.1 (the new pin, pulled by digest after the lead's yes): tests/storage 12 passed,
  test_the_database_under_test_is_the_managed_tiers_pgvector among them
```

## Verify
Fast checks during the loop: the storage suite against the pinned image, the unit, contract and
architecture suites, lint, types, the static gate. The full gate at the end of the loop is pasted
in record 027.

## Found by the first end-of-loop run
`make ci` was red on its first run: the four login tests errored in the pipeline's container with
`SocketConnectBlockedError` for the database sidecar's bridge address. The module lacked the
`pytestmark = pytest.mark.enable_socket` the other storage modules carry; locally the database had
been on 127.0.0.1, which the socket guard allows, so the gap did not show. The mark is added; the
run below is the second.

## Eval and budget numbers
This change's own numbers are in the record above; the run of every set, with each set's p95
latency and cost against its budget, is in the gate output below.

## The gate at the end of the loop
One full gate proves the whole tree of the loop, every record's change together.
```
$ make verify
(on the workstation, before four records' claims were corrected to CONTRACT — records only)
GATE GREEN (52 checks)
oasdiff: no breaking change against main
TOTAL                                                            7711     27    956     25    99%
1056 passed in 309.82s (0:05:09)
GATE GREEN (1 checks)
EVALS GREEN
GATE GREEN (1 checks)
No known vulnerabilities found
INF no leaks found
GATE GREEN (1 checks)
selftest: 54/54 checks red on their plant
VERIFY GREEN
exit=0 elapsed=628s
```
```
$ make ci
(in catalyst-ai-ci:d06a9811d6b3; the second run — the first was red: 1052 passed, 4 errors in
tests/storage/test_logins.py, SocketConnectBlockedError, fixed as record 031 says)
GATE GREEN (52 checks)
oasdiff: no breaking change against main
TOTAL                                                            7711     27    956     25    99%
1056 passed in 535.13s (0:08:55)
GATE GREEN (1 checks)
EVALS GREEN
GATE GREEN (1 checks)
No known vulnerabilities found
INF no leaks found
GATE GREEN (1 checks)
selftest: 54/54 checks red on their plant
VERIFY GREEN
stamp: tree b51a07c33c09 in catalyst-ai-ci:d06a9811d6b3 at 2026-09-24T12:03:29+00:00 -- green
exit=0 elapsed=1333s
```

## Commit
See the proposal list in record 027.
