"""The summarize operation: a bounded summary of items that names people only by their tokens."""

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from catalyst_ai.contract.envelopes import RequestEnvelope, ResponseEnvelope, classified

MAX_ITEMS = 200
MAX_ITEM_TEXT = 4_000
MAX_ITEM_ID = 64
MAX_TITLE = 500
MAX_TYPE = 64
MAX_STATUS = 64
MAX_STATUS_CHANGES = 100
MAX_LANGUAGE = 16
MAX_KIND = 64
MAX_COUNTS = 50
MAX_LINES = 12
MAX_LINE_CHARS = 300
KIND_SHAPE = r"^[a-z][a-z0-9_]{0,63}$"
WINDOW_MESSAGE = "window.to_at must not precede window.from_at"
MIN_TARGET_WORDS = 40
MAX_TARGET_WORDS = 400
DEFAULT_TARGET_WORDS = 150
MAX_SUMMARY_CHARS = 8_000
PARTICIPANT_SHAPE = r"^p[0-9]{1,4}$"
LANGUAGE_PATTERN = r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$"

EmptyReason = Literal["nothing_to_summarize"]
WINDOW_MODES = frozenset({"standup", "digest"})


class SummarizeMode(StrEnum):
    """`comments` is a work item's thread (decisions, blockers, questions); `thread` a talk."""

    COMMENTS = "comments"
    THREAD = "thread"
    STANDUP = "standup"
    DIGEST = "digest"


class ThreadItem(BaseModel):
    """One comment or message: who (a token the backend chose), when, what."""

    model_config = ConfigDict(extra="forbid")

    id: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_ITEM_ID,
            json_schema_extra=classified("INTERNAL", "The backend's id; returned in covered_range"),
        ),
    ]
    participant: Annotated[
        str,
        Field(
            pattern=PARTICIPANT_SHAPE,
            json_schema_extra=classified(
                "INTERNAL", "An opaque token (p1, p2, …) the backend maps back to a person"
            ),
        ),
    ]
    at: Annotated[datetime, Field(json_schema_extra=classified("INTERNAL", "When it was written"))]
    text: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_ITEM_TEXT,
            json_schema_extra=classified("CONFIDENTIAL", "The text as written"),
        ),
    ]
    kind: Annotated[
        str | None,
        Field(
            pattern=KIND_SHAPE,
            max_length=MAX_KIND,
            json_schema_extra=classified(
                "INTERNAL", "What the item is (work_item, comment, …); digest groups by it"
            ),
        ),
    ] = None


class Window(BaseModel):
    """The span a standup or digest covers; items outside it are left out."""

    model_config = ConfigDict(extra="forbid")

    from_at: datetime
    to_at: datetime

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.to_at < self.from_at:
            raise ValueError(WINDOW_MESSAGE)
        return self


class KindCount(BaseModel):
    """How many items of a kind changed in the window, as the backend counted them."""

    model_config = ConfigDict(extra="forbid")

    kind: str = Field(pattern=KIND_SHAPE, max_length=MAX_KIND)
    count: int = Field(ge=0)


class StatusChange(BaseModel):
    """A recorded status move, authoritative over anything the thread says about it."""

    model_config = ConfigDict(extra="forbid")

    participant: Annotated[
        str,
        Field(
            pattern=PARTICIPANT_SHAPE,
            json_schema_extra=classified("INTERNAL", "The token of who moved it"),
        ),
    ]
    from_status: Annotated[
        str | None,
        Field(max_length=MAX_STATUS, json_schema_extra=classified("INTERNAL", "The old status")),
    ] = None
    to_status: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_STATUS,
            json_schema_extra=classified("INTERNAL", "The new status"),
        ),
    ]
    at: Annotated[datetime, Field(json_schema_extra=classified("INTERNAL", "When"))]


class SummarizeRequest(RequestEnvelope):
    """The thread, its item, the recorded status changes, the length wanted."""

    model_config = ConfigDict(extra="forbid")

    mode: Annotated[
        SummarizeMode,
        Field(json_schema_extra=classified("PUBLIC", "Which prompt section and shape apply")),
    ]
    items: Annotated[
        list[ThreadItem],
        Field(
            max_length=MAX_ITEMS,
            json_schema_extra=classified("CONFIDENTIAL", "The thread, oldest first"),
        ),
    ]
    item_title: Annotated[
        str | None,
        Field(
            max_length=MAX_TITLE,
            json_schema_extra=classified(
                "CONFIDENTIAL", "The work item's title, when there is one"
            ),
        ),
    ] = None
    item_type: Annotated[
        str | None,
        Field(
            max_length=MAX_TYPE,
            json_schema_extra=classified("INTERNAL", "The work item's type; sets the focus"),
        ),
    ] = None
    status_changes: Annotated[
        list[StatusChange],
        Field(
            max_length=MAX_STATUS_CHANGES,
            json_schema_extra=classified("INTERNAL", "Recorded status moves, oldest first"),
        ),
    ] = Field(default_factory=list)
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
            json_schema_extra=classified(
                "PUBLIC", "BCP 47 tag of the summary; absent preserves the thread's"
            ),
        ),
    ] = None
    window: Annotated[
        Window | None,
        Field(
            json_schema_extra=classified(
                "INTERNAL", "The span a standup or digest covers; required by those modes"
            )
        ),
    ] = None
    counts: Annotated[
        list[KindCount],
        Field(
            max_length=MAX_COUNTS,
            json_schema_extra=classified(
                "INTERNAL", "The backend's counts per kind; a digest echoes them, never counts"
            ),
        ),
    ] = Field(default_factory=list)


class StandupEntry(BaseModel):
    """One participant's standup: what was done, what is in hand, what blocks — by token."""

    model_config = ConfigDict(extra="forbid")

    participant: str = Field(pattern=PARTICIPANT_SHAPE)
    done: list[str] = Field(max_length=MAX_LINES)
    doing: list[str] = Field(max_length=MAX_LINES)
    blocked: list[str] = Field(max_length=MAX_LINES)


class DigestGroup(BaseModel):
    """What changed for one kind in the window; the count is the backend's, echoed."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    count: int = Field(ge=0)
    changes: list[str] = Field(max_length=MAX_LINES)


class CoveredRange(BaseModel):
    """Which items the summary rests on: the first and last ids and how many."""

    model_config = ConfigDict(extra="forbid")

    first_id: str | None
    last_id: str | None
    count: int = Field(ge=0)


class SummarizeResponse(ResponseEnvelope):
    """The summary, or an empty one with its reason; the tokens it mentions; what it covered."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(max_length=MAX_SUMMARY_CHARS)
    empty_reason: EmptyReason | None
    covered_range: CoveredRange
    participants_mentioned: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    standup: list[StandupEntry] = Field(default_factory=list)
    digest: list[DigestGroup] = Field(default_factory=list)
