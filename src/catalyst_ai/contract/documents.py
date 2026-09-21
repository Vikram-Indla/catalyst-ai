"""The documents operations: ingest a hostile file, ask a space, draft from supplied sources."""

from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from catalyst_ai.contract.envelopes import RequestEnvelope, ResponseEnvelope, classified
from catalyst_ai.contract.search import HASH_PATTERN, KIND_PATTERN, IndexableClass

MAX_ID = 64
MAX_TITLE = 500
MAX_FILENAME = 255
MAX_BASE64 = 14_000_000
MAX_TEXT = 200_000
MAX_QUESTION = 2_000
MAX_BRIEF = 4_000
MAX_SOURCES = 40
MAX_SOURCE_TEXT = 20_000
MAX_ANSWER = 8_000
MAX_QUOTE = 300
MAX_CITATIONS = 40
MAX_SECTIONS = 30
MAX_HEADINGS = 200
MAX_LANGUAGE = 16
MIN_K = 1
MAX_K = 20
DEFAULT_K = 8
MIN_TARGET_WORDS = 100
MAX_TARGET_WORDS = 2_000
DEFAULT_TARGET_WORDS = 600
ID_SHAPE = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$"
LANGUAGE_PATTERN = r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$"
CONTENT_REQUIRED = "one of content_base64 or text is required, not both"

DocumentState = Literal["indexed", "unchanged"]
GenerateEmptyReason = Literal["sources_insufficient"]


class DocumentFormat(StrEnum):
    """The formats the parsers accept; anything else is `document_unsupported`."""

    DOCX = "docx"
    PPTX = "pptx"
    PDF = "pdf"
    MARKDOWN = "markdown"
    TEXT = "text"


class IngestRequest(RequestEnvelope):
    """One document: bytes or text, its format, its class, its space; never trusted."""

    model_config = ConfigDict(extra="forbid")

    space_id: Annotated[
        str,
        Field(
            pattern=ID_SHAPE,
            json_schema_extra=classified("INTERNAL", "The space the document belongs to"),
        ),
    ]
    document_id: Annotated[
        str,
        Field(
            pattern=ID_SHAPE,
            json_schema_extra=classified("INTERNAL", "The backend's id; every citation names it"),
        ),
    ]
    kind: Annotated[
        str,
        Field(
            pattern=KIND_PATTERN,
            json_schema_extra=classified("PUBLIC", "What the document is (wiki_page, attachment…)"),
        ),
    ]
    format: Annotated[
        DocumentFormat,
        Field(json_schema_extra=classified("PUBLIC", "The declared format; the bytes are checked")),
    ]
    filename: Annotated[
        str | None,
        Field(
            max_length=MAX_FILENAME,
            json_schema_extra=classified("INTERNAL", "For the record only; never opened"),
        ),
    ] = None
    title: Annotated[
        str | None,
        Field(max_length=MAX_TITLE, json_schema_extra=classified("CONFIDENTIAL", "The title")),
    ] = None
    content_base64: Annotated[
        str | None,
        Field(
            max_length=MAX_BASE64,
            json_schema_extra=classified(
                "CONFIDENTIAL", "The file's bytes, base64; parsed in a bounded subprocess"
            ),
        ),
    ] = None
    text: Annotated[
        str | None,
        Field(
            max_length=MAX_TEXT,
            json_schema_extra=classified(
                "CONFIDENTIAL", "Already-extracted text (markdown or plain) instead of bytes"
            ),
        ),
    ] = None
    data_class: Annotated[
        IndexableClass,
        Field(json_schema_extra=classified("PUBLIC", "The document's class; never RESTRICTED")),
    ]
    content_hash: Annotated[
        str,
        Field(
            pattern=HASH_PATTERN,
            json_schema_extra=classified(
                "INTERNAL", "sha256 of the bytes as the backend sent them; unchanged means no work"
            ),
        ),
    ]

    @model_validator(mode="after")
    def _one_content(self) -> Self:
        if (self.content_base64 is None) == (self.text is None):
            raise ValueError(CONTENT_REQUIRED)
        return self


class IngestResponse(ResponseEnvelope):
    """What the index now holds for the document."""

    model_config = ConfigDict(extra="forbid")

    document_id: str
    state: DocumentState
    chunks: int = Field(ge=0)
    headings: list[str] = Field(max_length=MAX_HEADINGS)
    embedding_model: str
    embedding_version: str
    index_chunks: int = Field(ge=0)


class AskRequest(RequestEnvelope):
    """A question over one space; the answer comes only from what the space's index holds."""

    model_config = ConfigDict(extra="forbid")

    space_id: Annotated[
        str,
        Field(pattern=ID_SHAPE, json_schema_extra=classified("INTERNAL", "The space asked")),
    ]
    question: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_QUESTION,
            json_schema_extra=classified("CONFIDENTIAL", "The member's question"),
        ),
    ]
    kinds: Annotated[
        list[str],
        Field(
            max_length=MAX_K,
            json_schema_extra=classified("PUBLIC", "Only documents of these kinds; empty = all"),
        ),
    ] = Field(default_factory=list)
    k: Annotated[
        int,
        Field(ge=MIN_K, le=MAX_K, json_schema_extra=classified("PUBLIC", "Chunks to read")),
    ] = DEFAULT_K
    language: Annotated[
        str | None,
        Field(
            max_length=MAX_LANGUAGE,
            pattern=LANGUAGE_PATTERN,
            json_schema_extra=classified("PUBLIC", "BCP 47 tag; absent follows the question's"),
        ),
    ] = None


class Citation(BaseModel):
    """One chunk an answer rests on: its id, its document, where in it, the words quoted."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: str
    document_id: str
    position: int = Field(ge=0)
    heading_path: list[str]
    quote: str = Field(max_length=MAX_QUOTE)


class AskResponse(ResponseEnvelope):
    """The answer with a citation behind every claim, or not found."""

    model_config = ConfigDict(extra="forbid")

    answer: str = Field(max_length=MAX_ANSWER)
    citations: list[Citation] = Field(max_length=MAX_CITATIONS)
    not_found: bool
    confidence: float = Field(ge=0.0, le=1.0)


class Source(BaseModel):
    """One supplied source a draft may cite."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=ID_SHAPE)
    title: str | None = Field(default=None, max_length=MAX_TITLE)
    text: str = Field(min_length=1, max_length=MAX_SOURCE_TEXT)


class DraftRequest(RequestEnvelope):
    """A brief and the sources it may draw on; nothing outside them enters the draft."""

    model_config = ConfigDict(extra="forbid")

    brief: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_BRIEF,
            json_schema_extra=classified("CONFIDENTIAL", "What the document should say"),
        ),
    ]
    sources: Annotated[
        list[Source],
        Field(
            min_length=1,
            max_length=MAX_SOURCES,
            json_schema_extra=classified("CONFIDENTIAL", "The texts with the ids sections cite"),
        ),
    ]
    target_words: Annotated[
        int,
        Field(
            ge=MIN_TARGET_WORDS,
            le=MAX_TARGET_WORDS,
            json_schema_extra=classified("PUBLIC", "The length wanted, in words"),
        ),
    ] = DEFAULT_TARGET_WORDS
    language: Annotated[
        str | None,
        Field(
            max_length=MAX_LANGUAGE,
            pattern=LANGUAGE_PATTERN,
            json_schema_extra=classified("PUBLIC", "BCP 47 tag; absent follows the brief's"),
        ),
    ] = None


class DraftSection(BaseModel):
    """One section of a draft with the sources it rests on."""

    model_config = ConfigDict(extra="forbid")

    heading: str = Field(min_length=1, max_length=MAX_TITLE)
    text: str = Field(min_length=1, max_length=MAX_ANSWER)
    sources: list[str] = Field(min_length=1, max_length=MAX_SOURCES)


class DraftResponse(ResponseEnvelope):
    """A draft whose every section cites, or nothing with its reason."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(max_length=MAX_TITLE)
    sections: list[DraftSection] = Field(max_length=MAX_SECTIONS)
    empty_reason: GenerateEmptyReason | None
    confidence: float = Field(ge=0.0, le=1.0)
