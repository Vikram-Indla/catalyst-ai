"""The Storage seam: the service's own database as typed operations; tests substitute it."""

from typing import Protocol
from uuid import UUID

from catalyst_ai.contract.search import Corpus
from catalyst_ai.platform.storage.rows import (
    ChunkRow,
    DocumentRecord,
    DocumentState,
    LexicalQuery,
    RetentionCut,
    SearchScope,
    StoredHit,
)


class Storage(Protocol):
    """Every query the service runs, scoped by organisation; the SQL lives in the query files."""

    async def ready(self) -> bool:
        """Return whether the database answers."""
        ...

    async def document_states(
        self, organization_id: UUID, corpus: Corpus, external_ids: list[str]
    ) -> dict[str, DocumentState]:
        """Return what the index holds for the keys, by key."""
        ...

    async def replace_document(self, document: DocumentRecord, chunks: list[ChunkRow]) -> None:
        """Store the document and its chunks, replacing whatever the key held before."""
        ...

    async def touch_document(self, organization_id: UUID, corpus: Corpus, external_id: str) -> None:
        """Mark an unchanged document as seen now."""
        ...

    async def read_document(
        self, organization_id: UUID, corpus: Corpus, external_id: str
    ) -> DocumentRecord | None:
        """Return the stored document or None."""
        ...

    async def delete_documents(
        self, organization_id: UUID, corpus: Corpus, external_ids: list[str]
    ) -> int:
        """Forget the keys; return how many chunks went with them."""
        ...

    async def count_chunks(self, organization_id: UUID, corpus: Corpus) -> int:
        """Return the size of the organisation's corpus in chunks."""
        ...

    async def search_vector(
        self, scope: SearchScope, vector: tuple[float, ...], model: str, version: str
    ) -> list[StoredHit]:
        """Return the nearest chunks at exactly this embedding model and version."""
        ...

    async def search_lexical(self, scope: SearchScope, query: LexicalQuery) -> list[StoredHit]:
        """Return the chunks the lexical leg ranks highest."""
        ...

    async def organizations(self, corpus: Corpus) -> list[UUID]:
        """Return every organisation with documents in the corpus (the maintenance role)."""
        ...

    async def stale_documents(
        self, organization_id: UUID, corpus: Corpus, model: str, version: str, limit: int
    ) -> list[str]:
        """Return keys whose embedding is not at the given model and version."""
        ...

    async def expired_documents(self, cut: RetentionCut) -> list[str]:
        """Return keys not seen since the cut."""
        ...

    async def remember_nonce(self, nonce: str, expires_at: int, now: int) -> bool:
        """Record a proof's nonce until it expires; False when it was seen before (a replay)."""
        ...
