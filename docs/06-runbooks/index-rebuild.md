# Index rebuild — re-embedding a corpus after a model or chunking change

**Applies to:** the `work_items` corpus (`retrieval/corpora.py`); later corpora add their line.

## When

- The register moves `embed-default` to another model id, or the corpus's `dimensions` or
  `revision` changes (a chunking change is a revision bump). Rows carry `embedding_model` and
  `embedding_version` (`d<dimensions>-r<revision>`); a search filters on exactly the current pair,
  so after such a change every un-re-embedded document is invisible to search until the job runs.
- A dimensions change also needs a migration (`vector(N)` on the chunks table) before the job.

## Steps

1. Announce in the contracts changelog (`embedding_version` changes for the backend).
2. Deploy the change; searches now return only re-embedded rows.
3. Run `catalyst-ai reembed` (the maintenance role: every organisation, stale documents in batches
   of 50, each batch one `index.upsert` pass through the same chunking and embedding path). It is
   idempotent: run it again until it reports `0 documents`.
4. Run the retrieval eval (`make evals` — the `search` set) and compare recall@10 and MRR with the
   previous row in `docs/04-ledgers/eval-sets.md`; a fall below a floor is a decision, not a deploy.
5. A full rebuild (rows lost, a corrupted index): the backend re-sends every document through
   `index.upsert`; identical `content_hash` values at the current version are touched, everything
   else is embedded. Nothing in this service needs to be restored from a backup for the index to
   converge (`ARCH-006 §5`).

## Cost

Re-embedding costs `embed-default`'s input price per token of every chunk once; the job's usage
rows are logged under capability `search`, organisation by organisation.

**The number, for the largest organisation** (500 000 chunks, per corpus): a chunk is at most
1 000 characters plus its title, about 275 tokens at four characters a token, so about 137.5 M
tokens. At the register's price (150 µ$ per 1 000 tokens, unverified in-region) that is about
**US$ 21**. The job sends 100 chunks a call, 5 000 calls in a row: about **70 minutes** if each call
takes the search budget's 800 ms, and up to **14 hours** if each takes its 10 s deadline. The
provider's quota may slow it further. The first live recording replaces the latency with a
measured one.

**A rebuild is never a release step.** Minutes to hours cannot sit between `migrate` and a
rollout: the release deploys, the old index keeps serving the rows it has, and an operator starts
`catalyst-ai reembed` (or the backend's re-send) as its own job afterwards.

## What a rebuild does not bring back

Rebuildable is not cheap, and two tables are not rebuildable at all: `provider_calls` (the cost
record, kept 90 days) and `tenant_budgets` (losing it resets every organisation's spend cap in the
middle of its window). They are why the database has a backup class (a daily snapshot plus
point-in-time recovery, `retention.md`), even though every index converges without one.
