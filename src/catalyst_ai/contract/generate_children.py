"""The generate-children operation: typed candidate children of a parent, never created here."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from catalyst_ai.contract.envelopes import RequestEnvelope, ResponseEnvelope, classified

MAX_TITLE = 500
MAX_TEXT = 20_000
MAX_SOURCES = 10
MAX_SIBLINGS = 100
MAX_LEVELS = 12
MIN_LEVELS = 2
MAX_LEVEL_NAME = 64
MAX_ITEMS = 20
DEFAULT_ITEMS = 7
MAX_HINT = 500
MAX_LANGUAGE = 16
MAX_KEY = 64
MAX_CRITERIA = 20
MAX_CRITERION = 1_000

EmptyReason = Literal["parent_too_vague", "siblings_cover_it", "nothing_at_this_level"]


class GenerateTarget(StrEnum):
    """What the caller wants: stories under an epic, epics under a request, or any next level."""

    STORIES = "stories"
    EPICS = "epics"
    CHILDREN = "children"


class Sibling(BaseModel):
    """An existing child the candidates must not repeat."""

    model_config = ConfigDict(extra="forbid")

    key: Annotated[
        str | None,
        Field(max_length=MAX_KEY, json_schema_extra=classified("INTERNAL", "The item key")),
    ] = None
    title: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_TITLE,
            json_schema_extra=classified("CONFIDENTIAL", "The title"),
        ),
    ]


class GenerateChildrenRequest(RequestEnvelope):
    """The parent, its context, the hierarchy as data, the siblings, and the bounds."""

    model_config = ConfigDict(extra="forbid")

    target: Annotated[
        GenerateTarget,
        Field(json_schema_extra=classified("PUBLIC", "Which prompt section and defaults apply")),
    ]
    hierarchy: Annotated[
        list[str],
        Field(
            min_length=MIN_LEVELS,
            max_length=MAX_LEVELS,
            json_schema_extra=classified(
                "INTERNAL", "The organisation's ordered levels, top first"
            ),
        ),
    ]
    parent_level: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_LEVEL_NAME,
            json_schema_extra=classified("INTERNAL", "The parent's level, one of hierarchy"),
        ),
    ]
    child_level: Annotated[
        str | None,
        Field(
            max_length=MAX_LEVEL_NAME,
            json_schema_extra=classified(
                "INTERNAL", "The wanted level; absent means the next one down"
            ),
        ),
    ] = None
    parent_title: Annotated[
        str,
        Field(
            max_length=MAX_TITLE, json_schema_extra=classified("CONFIDENTIAL", "The parent's title")
        ),
    ]
    parent_description: Annotated[
        str,
        Field(
            max_length=MAX_TEXT,
            json_schema_extra=classified("CONFIDENTIAL", "The parent's description"),
        ),
    ]
    source_texts: Annotated[
        list[str],
        Field(
            max_length=MAX_SOURCES,
            json_schema_extra=classified("CONFIDENTIAL", "Extracted text the backend attaches"),
        ),
    ] = Field(default_factory=list)
    siblings: Annotated[
        list[Sibling],
        Field(
            max_length=MAX_SIBLINGS,
            json_schema_extra=classified("CONFIDENTIAL", "Existing children at the wanted level"),
        ),
    ] = Field(default_factory=list)
    focus_hint: Annotated[
        str | None,
        Field(
            max_length=MAX_HINT,
            json_schema_extra=classified("CONFIDENTIAL", "What the member asked to focus on"),
        ),
    ] = None
    max_items: Annotated[
        int,
        Field(
            ge=1,
            le=MAX_ITEMS,
            json_schema_extra=classified("PUBLIC", "The most candidates to return"),
        ),
    ] = DEFAULT_ITEMS
    language: Annotated[
        str | None,
        Field(
            max_length=MAX_LANGUAGE,
            pattern=r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$",
            json_schema_extra=classified(
                "PUBLIC", "BCP 47 tag of the output; absent preserves the input's"
            ),
        ),
    ] = None


class Candidate(BaseModel):
    """One proposed child; the backend decides whether it becomes an item."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(min_length=1, max_length=MAX_LEVEL_NAME)
    title: str = Field(min_length=1, max_length=MAX_TITLE)
    description: str = Field(max_length=MAX_TEXT)
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=MAX_CRITERIA)
    confidence: float = Field(ge=0.0, le=1.0)
    duplicate_of: str | None = Field(default=None, max_length=MAX_TITLE)


class GenerateChildrenResponse(ResponseEnvelope):
    """Candidates, or an empty list with the reason; never an item written anywhere."""

    model_config = ConfigDict(extra="forbid")

    candidates: list[Candidate]
    empty_reason: EmptyReason | None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
