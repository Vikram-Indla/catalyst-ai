# documents-ingest — eval set (the parse matrix)

**Set version:** 1 · **Cases:** see `set.jsonl` — every sample of `tests/fixtures/documents/`:
the five benign formats indexed, one of them sent twice (`unchanged`), the hostile corpus
(`bomb.docx`, `macro.docx`, `nested.docx`, `entity.docx`, `traversal.docx`, `notzip.docx`,
`script.pdf`, `loop.pdf`, `notpdf.pdf`, `oversized.txt`, `control.txt`, `restricted.md`) each
expected as `ai.input.rejected` with its reason class, and the injected page indexed as text ·
**Provenance:** `tools/hostile.py` writes the samples; `tools/evalsets.py` writes the set.

## What a good output is

- A hostile sample is refused with exactly the expected class (`expected.refused`) — the harness
  scores a matching refusal 1.0 and any answer or other error 0.0.
- A benign sample is `indexed` the first time and `unchanged` the second (`state_as_expected`),
  yields at least one chunk (`chunks_present`), a heading for a structured format and none for
  plain text (`headings_seen`), and names its embedding model and version (`versions_named`).

## Graders

All deterministic (`graders.py`); every floor 1.0 — the matrix is not a score, it is a table.

## Fixtures

The embeddings are authored (`tools/authored.py`, hashed vectors); no model is called. The
numbers prove the parsers, the guards, the child runner and the class rule.
