"""Retrieval: corpora, chunking, embeddings and hybrid search over the service's own database."""

from catalyst_ai.retrieval.corpora import CORPORA, DOCUMENTS, WORK_ITEMS, CorpusSpec, spec_of
from catalyst_ai.retrieval.documents import (
    Passage,
    chunk_id,
    document_key,
    quote_for,
    space_prefix,
    windows_of,
)
from catalyst_ai.retrieval.grounding import Grounding, Retrieved, retrieve
from catalyst_ai.retrieval.ingest import Job, UpsertOutcome, delete, upsert
from catalyst_ai.retrieval.jobs import Report, reembed, retention
from catalyst_ai.retrieval.search import Found, Query, search

__all__ = [
    "CORPORA",
    "DOCUMENTS",
    "WORK_ITEMS",
    "CorpusSpec",
    "Found",
    "Grounding",
    "Job",
    "Passage",
    "Query",
    "Report",
    "Retrieved",
    "UpsertOutcome",
    "chunk_id",
    "delete",
    "document_key",
    "quote_for",
    "reembed",
    "retention",
    "retrieve",
    "search",
    "space_prefix",
    "spec_of",
    "upsert",
    "windows_of",
]
