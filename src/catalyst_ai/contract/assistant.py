"""The assistant's one operation: a bounded conversation answered from supplied context only.

No tool, no fetch, no memory: the backend keeps the conversation, chooses what the reply may see
and enforces who may see it. The reply cites every source it used or says it found nothing.
"""

from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from catalyst_ai.contract.documents import Citation
from catalyst_ai.contract.envelopes import RequestEnvelope, ResponseEnvelope, classified

MAX_TURNS = 20
MAX_TURN_TEXT = 4_000
MAX_SUMMARY = 2_000
MAX_ITEMS = 50
MAX_SPACES = 10
MAX_PAGES = 5
MAX_PAGE_TEXT = 20_000
MAX_TITLE = 500
MAX_ITEM_SUMMARY = 2_000
MAX_KEY = 64
MAX_REPLY = 6_000
MAX_CITATIONS = 40
MAX_LANGUAGE = 16
ID_SHAPE = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$"
KIND_SHAPE = r"^[a-z][a-z0-9_]{0,63}$"
LANGUAGE_PATTERN = r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$"
LAST_TURN_IS_USER = "the last turn must be the member's"

Role = Literal["user", "assistant"]
SourceKind = Literal["passage", "item", "page"]


class Turn(BaseModel):
    """One message of the thread the backend keeps; the service remembers nothing between calls."""

    model_config = ConfigDict(extra="forbid")

    role: Role
    text: str = Field(min_length=1, max_length=MAX_TURN_TEXT)


class ContextItem(BaseModel):
    """A work item the backend decided this member may see, as facts — never a query result."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=ID_SHAPE)
    key: str | None = Field(default=None, max_length=MAX_KEY)
    kind: str = Field(pattern=KIND_SHAPE)
    title: str = Field(min_length=1, max_length=MAX_TITLE)
    status: str | None = Field(default=None, max_length=MAX_KEY)
    summary: str | None = Field(default=None, max_length=MAX_ITEM_SUMMARY)


class ContextSpace(BaseModel):
    """A space the reply may read through the documents index; membership is the backend's."""

    model_config = ConfigDict(extra="forbid")

    space_id: str = Field(pattern=ID_SHAPE)
    title: str | None = Field(default=None, max_length=MAX_TITLE)


class ContextPage(BaseModel):
    """A page's text the backend supplies whole; shown as one numbered source."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=ID_SHAPE)
    title: str | None = Field(default=None, max_length=MAX_TITLE)
    text: str = Field(min_length=1, max_length=MAX_PAGE_TEXT)


class Context(BaseModel):
    """Everything the reply may know: chosen, scoped and classified by the backend."""

    model_config = ConfigDict(extra="forbid")

    items: list[ContextItem] = Field(default_factory=list, max_length=MAX_ITEMS)
    spaces: list[ContextSpace] = Field(default_factory=list, max_length=MAX_SPACES)
    pages: list[ContextPage] = Field(default_factory=list, max_length=MAX_PAGES)


class TurnRequest(RequestEnvelope):
    """The thread (bounded), the backend's digest of what fell off it, and the context."""

    model_config = ConfigDict(extra="forbid")

    history: Annotated[
        list[Turn],
        Field(
            min_length=1,
            max_length=MAX_TURNS,
            json_schema_extra=classified("CONFIDENTIAL", "The thread, oldest first"),
        ),
    ]
    summary: Annotated[
        str | None,
        Field(
            max_length=MAX_SUMMARY,
            json_schema_extra=classified(
                "CONFIDENTIAL", "The backend's summary of the turns it no longer sends"
            ),
        ),
    ] = None
    context: Annotated[
        Context,
        Field(
            json_schema_extra=classified(
                "CONFIDENTIAL", "What this member may see; decided and scoped by the backend"
            )
        ),
    ] = Field(default_factory=Context)
    language: Annotated[
        str | None,
        Field(
            max_length=MAX_LANGUAGE,
            pattern=LANGUAGE_PATTERN,
            json_schema_extra=classified("PUBLIC", "BCP 47 tag of the reply; else the thread's"),
        ),
    ] = None

    @model_validator(mode="after")
    def _ends_with_the_member(self) -> Self:
        if self.history[-1].role != "user":
            raise ValueError(LAST_TURN_IS_USER)
        return self


class TurnSource(BaseModel):
    """One source the reply cites, under the marker the reply carries.

    A passage of the index carries its chunk citation; an item or a page carries its id.
    """

    model_config = ConfigDict(extra="forbid")

    marker: int = Field(ge=1)
    kind: SourceKind
    source_id: str
    citation: Citation | None = None


class TurnResponse(ResponseEnvelope):
    """The reply with what it rests on, or nothing found; `[n]` in the reply names `sources`."""

    model_config = ConfigDict(extra="forbid")

    reply: str = Field(max_length=MAX_REPLY)
    sources: list[TurnSource] = Field(max_length=MAX_CITATIONS)
    not_found: bool
    confidence: float = Field(ge=0.0, le=1.0)
