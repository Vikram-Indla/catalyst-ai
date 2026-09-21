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
