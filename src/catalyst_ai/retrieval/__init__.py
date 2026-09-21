"""Retrieval: corpora, chunking, embeddings and hybrid search over the service's own database."""

from catalyst_ai.retrieval.corpora import CORPORA, WORK_ITEMS, CorpusSpec, spec_of
from catalyst_ai.retrieval.ingest import Job, UpsertOutcome, delete, upsert
from catalyst_ai.retrieval.jobs import Report, reembed, retention
from catalyst_ai.retrieval.search import Found, Query, search

__all__ = [
    "CORPORA",
    "WORK_ITEMS",
    "CorpusSpec",
    "Found",
    "Job",
    "Query",
    "Report",
    "UpsertOutcome",
    "delete",
    "reembed",
    "retention",
    "search",
    "spec_of",
    "upsert",
]
