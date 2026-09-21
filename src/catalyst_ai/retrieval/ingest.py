"""Indexing: what changed is chunked and embedded, what did not is touched, the budget is a wall."""

from dataclasses import dataclass

from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.contract.errors import ErrorCode, ErrorDetail
from catalyst_ai.contract.search import IndexDocument
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.storage import (
    ChunkRow,
    DocumentRecord,
    DocumentState,
    Storage,
    StorageUnavailableError,
)
from catalyst_ai.providers.port import Provider
from catalyst_ai.retrieval.chunking import chunk, embedding_input
from catalyst_ai.retrieval.corpora import CorpusSpec
from catalyst_ai.retrieval.embeddings import NO_USAGE, EmbedContext, Embedded, embed_texts

INDEX_BUDGET = "index_budget"
DOCUMENT_TOO_LARGE = "document_too_large"


@dataclass(frozen=True)
class IndexedOutcome:
    """What happened to one document."""

    external_id: str
    chunks: int
    embedding_model: str
    embedding_version: str
    unchanged: bool


@dataclass(frozen=True)
class UpsertOutcome:
    """The per-document outcomes, the corpus size afterwards, and the embedding usage."""

    results: list[IndexedOutcome]
    index_chunks: int
    usage: Usage
    model_id: str


@dataclass(frozen=True)
class Job(EmbedContext):
    """The embedding context plus the organisation's index budget."""

    max_chunks: int


def index_unavailable(error: StorageUnavailableError) -> Error:
    """Map a storage failure to the catalog; the kind goes to the log, never onward."""
    return Error(ErrorCode.INDEX_UNAVAILABLE, "the index is unavailable", retry_after_ms=5_000)


def refuse_oversized(documents: list[IndexDocument], spec: CorpusSpec) -> None:
    """Refuse the whole call before any embedding when a document is over the corpus limit."""
    oversized = [d.external_id for d in documents if len(d.text) > spec.max_document_chars]
    if oversized:
        details = [
            ErrorDetail(
                field="documents", code=DOCUMENT_TOO_LARGE, message=f"{len(oversized)} over"
            )
        ]
        raise Error(
            ErrorCode.INDEX_DOCUMENT_TOO_LARGE,
            "a document exceeds the corpus limit",
            details=details,
        )


def _unchanged(
    document: IndexDocument, state: DocumentState | None, model: str, spec: CorpusSpec
) -> bool:
    return (
        state is not None
        and state.content_hash == document.content_hash
        and state.embedding_model == model
        and state.embedding_version == spec.version
    )


def _refuse_over_budget(current: int, freed: int, added: int, job: Job) -> None:
    if current - freed + added > job.max_chunks:
        details = [
            ErrorDetail(field="documents", code=INDEX_BUDGET, message="over the index budget")
        ]
        raise Error(ErrorCode.BUDGET_EXCEEDED, "the organisation's index is full", details=details)


async def _store(
    job: Job, storage: Storage, document: IndexDocument, windows: list[str], embedded: Embedded
) -> IndexedOutcome:
    record = DocumentRecord(
        organization_id=job.organization_id,
        corpus=job.spec.name,
        external_id=document.external_id,
        kind=document.kind,
        title=document.title,
        text=document.text,
        content_hash=document.content_hash,
        data_class=document.data_class,
        embedding_model=embedded.model_id,
        embedding_version=job.spec.version,
    )
    rows = [
        ChunkRow(chunk_index=i, text=window, embedding=embedded.vectors[i])
        for i, window in enumerate(windows)
    ]
    await storage.replace_document(record, rows)
    return IndexedOutcome(
        document.external_id, len(rows), embedded.model_id, job.spec.version, unchanged=False
    )


async def upsert(
    job: Job, documents: list[IndexDocument], storage: Storage, provider: Provider
) -> UpsertOutcome:
    """Index the changed documents in one embedding pass; touch the unchanged ones."""
    refuse_oversized(documents, job.spec)
    model = provider.model_id(job.spec.alias)
    try:
        states = await storage.document_states(
            job.organization_id, job.spec.name, [d.external_id for d in documents]
        )
        changed = [
            d for d in documents if not _unchanged(d, states.get(d.external_id), model, job.spec)
        ]
        windows = {d.external_id: chunk(d.text, job.spec) for d in changed}
        current = await storage.count_chunks(job.organization_id, job.spec.name)
        freed = sum(states[d.external_id].chunks for d in changed if d.external_id in states)
        _refuse_over_budget(current, freed, sum(len(w) for w in windows.values()), job)
        texts = [embedding_input(d.title, w) for d in changed for w in windows[d.external_id]]
        embedded = await embed_texts(provider, job, texts, "document")
        results: dict[str, IndexedOutcome] = {}
        offset = 0
        for document in changed:
            count = len(windows[document.external_id])
            part = Embedded(embedded.vectors[offset : offset + count], embedded.model_id, NO_USAGE)
            results[document.external_id] = await _store(
                job, storage, document, windows[document.external_id], part
            )
            offset += count
        for document in documents:
            if document.external_id not in results:
                await storage.touch_document(
                    job.organization_id, job.spec.name, document.external_id
                )
                state = states[document.external_id]
                results[document.external_id] = IndexedOutcome(
                    document.external_id, state.chunks, model, job.spec.version, unchanged=True
                )
        total = await storage.count_chunks(job.organization_id, job.spec.name)
    except StorageUnavailableError as error:
        raise index_unavailable(error) from error
    ordered = [results[d.external_id] for d in documents]
    usage = embedded.usage if changed else NO_USAGE
    return UpsertOutcome(ordered, total, usage, embedded.model_id if changed else model)


async def delete(job: Job, external_ids: list[str], storage: Storage) -> int:
    """Forget the keys; return the chunks removed."""
    try:
        return await storage.delete_documents(job.organization_id, job.spec.name, external_ids)
    except StorageUnavailableError as error:
        raise index_unavailable(error) from error
