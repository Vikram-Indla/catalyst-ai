"""The values that cross the Storage seam: chunk rows, document states, hits and scopes."""

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from catalyst_ai.contract.search import Corpus, IndexableClass

TABLE_PREFIX_DOCUMENTS = "index_documents_"
TABLE_PREFIX_CHUNKS = "embeddings_"


@dataclass(frozen=True)
class DocumentRecord:
    """A document as the backend sent it, with the embedding it was indexed under."""

    organization_id: UUID
    corpus: Corpus
    external_id: str
    kind: str
    title: str | None
    text: str
    content_hash: str
    data_class: IndexableClass
    embedding_model: str
    embedding_version: str


@dataclass(frozen=True)
class ChunkRow:
    """One embedded window of a document."""

    chunk_index: int
    text: str
    embedding: tuple[float, ...]


@dataclass(frozen=True)
class DocumentState:
    """What the index holds for a key: enough to decide whether to re-embed."""

    external_id: str
    content_hash: str
    embedding_model: str
    embedding_version: str
    chunks: int


@dataclass(frozen=True)
class StoredHit:
    """One chunk a search leg returned, with that leg's own score."""

    external_id: str
    kind: str
    title: str | None
    chunk_index: int
    text: str
    embedding_model: str
    embedding_version: str
    score: float


@dataclass(frozen=True)
class SearchScope:
    """The tenant, the corpus and the filters every search leg applies before ranking.

    `prefix` narrows to keys that start with it — a space inside an organisation.
    """

    organization_id: UUID
    corpus: Corpus
    kinds: tuple[str, ...]
    exclude: tuple[str, ...]
    limit: int
    prefix: str = ""


@dataclass(frozen=True)
class LexicalQuery:
    """A lexical leg: `any` matches any listed token, `web` is a member's query with phrases."""

    form: str
    text: str


@dataclass(frozen=True)
class RetentionCut:
    """Documents not seen since the instant are due for the retention job."""

    organization_id: UUID
    corpus: Corpus
    before: datetime
    limit: int


def documents_table(corpus: Corpus) -> str:
    """Return the documents table of a corpus."""
    return f"{TABLE_PREFIX_DOCUMENTS}{corpus}"


def chunks_table(corpus: Corpus) -> str:
    """Return the chunks table of a corpus."""
    return f"{TABLE_PREFIX_CHUNKS}{corpus}"
