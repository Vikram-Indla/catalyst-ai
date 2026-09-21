"""MemoryStorage: the seam in a dictionary; unit tests and evals without a database run here."""

import math
import re
from datetime import datetime
from uuid import UUID

from catalyst_ai.contract.search import Corpus
from catalyst_ai.platform.clock import Clock
from catalyst_ai.platform.storage.rows import (
    ChunkRow,
    DocumentRecord,
    DocumentState,
    LexicalQuery,
    RetentionCut,
    SearchScope,
    StoredHit,
)

TOKEN = re.compile(r"[^\W_]+", re.UNICODE)
PHRASE = re.compile(r'"([^"]+)"')
Key = tuple[UUID, Corpus, str]


def _tokens(text: str) -> set[str]:
    return set(TOKEN.findall(text.lower()))


def cosine(left: tuple[float, ...], right: tuple[float, ...]) -> float:
    """Return the cosine similarity of two vectors; zero when either is null."""
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    norms = math.sqrt(sum(a * a for a in left)) * math.sqrt(sum(b * b for b in right))
    return dot / norms if norms else 0.0


def _web_score(query_text: str, haystack: str, present: set[str]) -> float:
    phrases = PHRASE.findall(query_text)
    words = _tokens(PHRASE.sub(" ", query_text))
    missing_phrase = any(phrase.lower() not in haystack for phrase in phrases)
    if missing_phrase or not words <= present:
        return 0.0
    return 1.0 + (len(words) + len(phrases)) / max(1, len(present))


def lexical_score(query: LexicalQuery, title: str | None, text: str) -> float:
    """Score one chunk: `any` counts matched tokens; `web` requires every token and phrase."""
    haystack = f"{title or ''} {text}".lower()
    present = _tokens(haystack)
    if query.form == "any":
        wanted = _tokens(query.text)
        return len(wanted & present) / len(wanted) if wanted else 0.0
    return _web_score(query.text, haystack, present)


class MemoryStorage:
    """Documents and chunks per (organisation, corpus, key), searched by brute force."""

    def __init__(self, clock: Clock) -> None:
        """Bind the clock that stamps `last_seen_at`."""
        self._clock = clock
        self._documents: dict[Key, DocumentRecord] = {}
        self._chunks: dict[Key, list[ChunkRow]] = {}
        self._seen: dict[Key, datetime] = {}

    async def ready(self) -> bool:
        """Answer always."""
        return True

    async def document_states(
        self, organization_id: UUID, corpus: Corpus, external_ids: list[str]
    ) -> dict[str, DocumentState]:
        """Return the state of every key the store holds."""
        states = {}
        for external_id in external_ids:
            key = (organization_id, corpus, external_id)
            document = self._documents.get(key)
            if document is not None:
                states[external_id] = DocumentState(
                    external_id,
                    document.content_hash,
                    document.embedding_model,
                    document.embedding_version,
                    len(self._chunks[key]),
                )
        return states

    async def replace_document(self, document: DocumentRecord, chunks: list[ChunkRow]) -> None:
        """Store or overwrite the key."""
        key = (document.organization_id, document.corpus, document.external_id)
        self._documents[key] = document
        self._chunks[key] = list(chunks)
        self._seen[key] = self._clock.now()

    async def touch_document(self, organization_id: UUID, corpus: Corpus, external_id: str) -> None:
        """Stamp the key as seen now."""
        self._seen[organization_id, corpus, external_id] = self._clock.now()

    async def read_document(
        self, organization_id: UUID, corpus: Corpus, external_id: str
    ) -> DocumentRecord | None:
        """Return the stored document or None."""
        return self._documents.get((organization_id, corpus, external_id))

    async def delete_documents(
        self, organization_id: UUID, corpus: Corpus, external_ids: list[str]
    ) -> int:
        """Drop the keys; return the chunks dropped."""
        dropped = 0
        for external_id in external_ids:
            key = (organization_id, corpus, external_id)
            if key in self._documents:
                dropped += len(self._chunks.pop(key))
                del self._documents[key]
                self._seen.pop(key, None)
        return dropped

    async def count_chunks(self, organization_id: UUID, corpus: Corpus) -> int:
        """Return the organisation's chunk count in the corpus."""
        return sum(
            len(rows)
            for (org, cor, _), rows in self._chunks.items()
            if org == organization_id and cor == corpus
        )

    def _in_scope(self, scope: SearchScope) -> list[tuple[DocumentRecord, ChunkRow]]:
        pairs: list[tuple[DocumentRecord, ChunkRow]] = []
        for key, document in self._documents.items():
            if key[0] != scope.organization_id or key[1] != scope.corpus:
                continue
            if scope.kinds and document.kind not in scope.kinds:
                continue
            if document.external_id in scope.exclude:
                continue
            if not document.external_id.startswith(scope.prefix):
                continue
            pairs.extend((document, chunk) for chunk in self._chunks[key])
        return pairs

    async def search_vector(
        self, scope: SearchScope, vector: tuple[float, ...], model: str, version: str
    ) -> list[StoredHit]:
        """Rank by cosine similarity at exactly the model and version."""
        scored = [
            _hit(document, chunk, cosine(vector, chunk.embedding))
            for document, chunk in self._in_scope(scope)
            if document.embedding_model == model and document.embedding_version == version
        ]
        scored.sort(key=lambda hit: (-hit.score, hit.external_id, hit.chunk_index))
        return scored[: scope.limit]

    async def search_lexical(self, scope: SearchScope, query: LexicalQuery) -> list[StoredHit]:
        """Rank by the lexical score; chunks that match nothing are not hits."""
        scored = [
            _hit(document, chunk, lexical_score(query, document.title, chunk.text))
            for document, chunk in self._in_scope(scope)
        ]
        hits = [hit for hit in scored if hit.score > 0.0]
        hits.sort(key=lambda hit: (-hit.score, hit.external_id, hit.chunk_index))
        return hits[: scope.limit]

    async def organizations(self, corpus: Corpus) -> list[UUID]:
        """Return every organisation with a document in the corpus, sorted."""
        return sorted({org for (org, cor, _) in self._documents if cor == corpus})

    async def stale_documents(
        self, organization_id: UUID, corpus: Corpus, model: str, version: str, limit: int
    ) -> list[str]:
        """Return keys not embedded at the model and version, in key order."""
        stale = [
            document.external_id
            for (org, cor, _), document in sorted(self._documents.items())
            if org == organization_id
            and cor == corpus
            and (document.embedding_model != model or document.embedding_version != version)
        ]
        return stale[:limit]

    async def expired_documents(self, cut: RetentionCut) -> list[str]:
        """Return keys last seen before the cut, oldest first."""
        due = [
            (seen, key[2])
            for key, seen in self._seen.items()
            if key[0] == cut.organization_id and key[1] == cut.corpus and seen < cut.before
        ]
        return [external_id for _, external_id in sorted(due)[: cut.limit]]


def _hit(document: DocumentRecord, chunk: ChunkRow, score: float) -> StoredHit:
    return StoredHit(
        external_id=document.external_id,
        kind=document.kind,
        title=document.title,
        chunk_index=chunk.chunk_index,
        text=chunk.text,
        embedding_model=document.embedding_model,
        embedding_version=document.embedding_version,
        score=score,
    )
