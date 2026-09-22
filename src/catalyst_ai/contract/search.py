"""The retrieval operations: what the backend indexes, what it deletes, and what it searches."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from catalyst_ai.contract.envelopes import RequestEnvelope, ResponseEnvelope, classified

MAX_DOCUMENTS = 100
MAX_DELETE_IDS = 500
MAX_EXTERNAL_ID = 200
MAX_KIND = 40
MAX_TITLE = 500
MAX_DOCUMENT_CHARS = 20_000
MAX_QUERY_CHARS = 4_000
MAX_EXCLUDE = 100
MAX_KINDS = 20
MAX_K = 50
DEFAULT_K = 10
HASH_PATTERN = r"^[0-9a-f]{64}$"
KIND_PATTERN = r"^[a-z][a-z0-9_]{0,39}$"
MAX_SNIPPET = 240

Corpus = Literal["work_items", "documents"]
SearchCorpus = Literal["work_items"]
IndexableClass = Literal["PUBLIC", "INTERNAL", "CONFIDENTIAL"]


class SearchMode(StrEnum):
    """`similar` ranks against an item's own text; `query` ranks against a member's words."""

    SIMILAR = "similar"
    QUERY = "query"


class IndexDocument(BaseModel):
    """One document the backend wants findable: its text, its key, its class, its hash."""

    model_config = ConfigDict(extra="forbid")

    external_id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_EXTERNAL_ID,
            json_schema_extra=classified("INTERNAL", "The backend's key for the document"),
        ),
    ]
    kind: Annotated[
        str,
        Field(
            pattern=KIND_PATTERN,
            json_schema_extra=classified("PUBLIC", "The item level or type, a filter for search"),
        ),
    ]
    title: Annotated[
        str | None,
        Field(
            max_length=MAX_TITLE,
            json_schema_extra=classified("CONFIDENTIAL", "The title, returned with every hit"),
        ),
    ] = None
    text: Annotated[
        str,
        Field(
            min_length=1,
            json_schema_extra=classified(
                "CONFIDENTIAL", "The text to index; over the corpus limit is refused"
            ),
        ),
    ]
    data_class: Annotated[
        IndexableClass,
        Field(json_schema_extra=classified("PUBLIC", "The document's class; never RESTRICTED")),
    ]
    content_hash: Annotated[
        str,
        Field(
            pattern=HASH_PATTERN,
            json_schema_extra=classified(
                "INTERNAL", "sha256 of title and text; an unchanged hash is not re-embedded"
            ),
        ),
    ]


class IndexUpsertRequest(RequestEnvelope):
    """Documents to index or re-index in one corpus of the caller's organisation."""

    model_config = ConfigDict(extra="forbid")

    corpus: Annotated[
        SearchCorpus,
        Field(json_schema_extra=classified("PUBLIC", "Which corpus the documents join")),
    ]
    documents: Annotated[
        list[IndexDocument],
        Field(
            min_length=1,
            max_length=MAX_DOCUMENTS,
            json_schema_extra=classified("CONFIDENTIAL", "The documents"),
        ),
    ]


class IndexedDocument(BaseModel):
    """What happened to one document."""

    model_config = ConfigDict(extra="forbid")

    external_id: str
    chunks: int = Field(ge=0)
    embedding_model: str
    embedding_version: str
    unchanged: bool


class IndexUpsertResult(ResponseEnvelope):
    """One line per document and the corpus size afterwards."""

    model_config = ConfigDict(extra="forbid")

    results: list[IndexedDocument]
    index_chunks: int = Field(ge=0)


class IndexDeleteRequest(RequestEnvelope):
    """Documents to forget, by key."""

    model_config = ConfigDict(extra="forbid")

    corpus: Annotated[
        SearchCorpus,
        Field(json_schema_extra=classified("PUBLIC", "Which corpus the keys belong to")),
    ]
    external_ids: Annotated[
        list[str],
        Field(
            min_length=1,
            max_length=MAX_DELETE_IDS,
            json_schema_extra=classified("INTERNAL", "The backend's keys"),
        ),
    ]


class IndexDeleteResult(ResponseEnvelope):
    """How many chunks were removed."""

    model_config = ConfigDict(extra="forbid")

    deleted_chunks: int = Field(ge=0)


class SearchRequest(RequestEnvelope):
    """A search over one corpus: by an item's text or by a member's query."""

    model_config = ConfigDict(extra="forbid")

    corpus: Annotated[
        SearchCorpus, Field(json_schema_extra=classified("PUBLIC", "Which corpus to search"))
    ]
    mode: Annotated[
        SearchMode,
        Field(json_schema_extra=classified("PUBLIC", "similar (an item's text) or query")),
    ]
    text: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_QUERY_CHARS,
            json_schema_extra=classified("CONFIDENTIAL", "The item's text or the member's query"),
        ),
    ]
    kinds: Annotated[
        list[str],
        Field(
            max_length=MAX_KINDS,
            json_schema_extra=classified("PUBLIC", "Only hits of these kinds; empty means all"),
        ),
    ] = Field(default_factory=list)
    exclude_external_ids: Annotated[
        list[str],
        Field(
            max_length=MAX_EXCLUDE,
            json_schema_extra=classified(
                "INTERNAL", "Keys never returned: the item itself, what is already linked"
            ),
        ),
    ] = Field(default_factory=list)
    k: Annotated[
        int,
        Field(ge=1, le=MAX_K, json_schema_extra=classified("PUBLIC", "How many hits at most")),
    ] = DEFAULT_K


class Provenance(BaseModel):
    """Where a hit comes from and how each leg of the ranking placed it."""

    model_config = ConfigDict(extra="forbid")

    chunk_index: int = Field(ge=0)
    embedding_model: str
    embedding_version: str
    vector_rank: int | None = Field(default=None, ge=1)
    lexical_rank: int | None = Field(default=None, ge=1)
    vector_similarity: float | None = Field(default=None, ge=-1.0, le=1.0)


class Hit(BaseModel):
    """One document the search found, with the score of the documented fusion."""

    model_config = ConfigDict(extra="forbid")

    external_id: str
    kind: str
    title: str | None
    score: float = Field(ge=0.0, le=1.0)
    snippet: str = Field(max_length=MAX_SNIPPET)
    provenance: Provenance


class SearchResponse(ResponseEnvelope):
    """The hits in rank order, and the fusion and embedding version that ranked them."""

    model_config = ConfigDict(extra="forbid")

    hits: list[Hit]
    fusion: str
    embedding_version: str
