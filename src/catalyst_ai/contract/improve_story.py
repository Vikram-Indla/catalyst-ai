"""The improve-story operation: a rewrite of a work item's text under one editorial mode.

Two modes work on a comment rather than the item: `polish_comment` rewrites the comment clearly in
its own language, and `reply` suggests a reply to it, with the item as context. People appear only
as the backend's tokens: the comment's author is one, and every mention in the comment's text must
be one (`@p1`); a comment that mentions anyone by name is refused at the door.
"""

import re
from enum import StrEnum
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from catalyst_ai.contract.envelopes import RequestEnvelope, ResponseEnvelope, classified

MAX_TITLE = 500
MAX_TEXT = 20_000
MAX_CRITERIA = 10_000
MAX_HINT = 500
MAX_TYPE = 64
MAX_LANGUAGE = 16
MAX_COMMENT = 4_000
PARTICIPANT_SHAPE = r"^p[0-9]{1,4}$"
MENTION = re.compile(r"(?<![\w.])@(?P<handle>[\w-]+(?:\.[\w-]+)*)")
TOKEN = re.compile(PARTICIPANT_SHAPE)
NAMED_MENTION = "a mention must be a participant token such as @p1, never a name"
COMMENT_NEEDED = "polish_comment and reply need `comment`; the other modes take none"


class ImproveStoryMode(StrEnum):
    """The editorial operations; each maps to one instruction block of the prompt."""

    CLARIFY = "clarify"
    EXPAND = "expand"
    ACCEPTANCE_CRITERIA = "acceptance_criteria"
    USER_STORY = "user_story"
    SHORTEN = "shorten"
    EDGE_CASES = "edge_cases"
    POLISH_COMMENT = "polish_comment"
    REPLY = "reply"


COMMENT_MODES = frozenset({ImproveStoryMode.POLISH_COMMENT, ImproveStoryMode.REPLY})


def named_mentions(text: str) -> list[str]:
    """Return every mention in the text that is not a participant token."""
    return [m.group("handle") for m in MENTION.finditer(text) if not TOKEN.match(m.group("handle"))]


class CommentInput(BaseModel):
    """A comment, as the backend sends it: its author and every mention are tokens it chose."""

    model_config = ConfigDict(extra="forbid")

    participant: Annotated[
        str,
        Field(
            pattern=PARTICIPANT_SHAPE,
            json_schema_extra=classified(
                "INTERNAL", "An opaque token (p1, p2, …) for the comment's author"
            ),
        ),
    ]
    text: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_COMMENT,
            json_schema_extra=classified(
                "CONFIDENTIAL", "The comment as written; people only as @p<N> mentions"
            ),
        ),
    ]

    @field_validator("text")
    @classmethod
    def _mentions_are_tokens(cls, value: str) -> str:
        if named_mentions(value):
            raise ValueError(NAMED_MENTION)
        return value


class ImproveStoryRequest(RequestEnvelope):
    """What the backend sends: the item's text, classified, and the mode."""

    model_config = ConfigDict(extra="forbid")

    mode: Annotated[
        ImproveStoryMode, Field(json_schema_extra=classified("PUBLIC", "The editorial operation"))
    ]
    item_type: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_TYPE,
            json_schema_extra=classified(
                "INTERNAL", "The work item type name, as the product names it"
            ),
        ),
    ]
    title: Annotated[
        str,
        Field(max_length=MAX_TITLE, json_schema_extra=classified("CONFIDENTIAL", "The item title")),
    ]
    description: Annotated[
        str,
        Field(
            max_length=MAX_TEXT,
            json_schema_extra=classified("CONFIDENTIAL", "The current description, markdown"),
        ),
    ]
    acceptance_criteria: Annotated[
        str | None,
        Field(
            max_length=MAX_CRITERIA,
            json_schema_extra=classified(
                "CONFIDENTIAL", "The current acceptance criteria, markdown"
            ),
        ),
    ] = None
    focus_hint: Annotated[
        str | None,
        Field(
            max_length=MAX_HINT,
            json_schema_extra=classified("CONFIDENTIAL", "What the member asked to focus on"),
        ),
    ] = None
    parent_title: Annotated[
        str | None,
        Field(
            max_length=MAX_TITLE, json_schema_extra=classified("CONFIDENTIAL", "The parent's title")
        ),
    ] = None
    parent_description: Annotated[
        str | None,
        Field(
            max_length=MAX_TEXT,
            json_schema_extra=classified(
                "CONFIDENTIAL", "The parent's description, read-only context"
            ),
        ),
    ] = None
    language: Annotated[
        str | None,
        Field(
            max_length=MAX_LANGUAGE,
            pattern=r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$",
            json_schema_extra=classified(
                "PUBLIC", "BCP 47 tag of the output; absent means the input's language is preserved"
            ),
        ),
    ] = None
    comment: Annotated[
        CommentInput | None,
        Field(
            json_schema_extra=classified(
                "CONFIDENTIAL", "polish_comment: the comment; reply: the comment replied to"
            ),
        ),
    ] = None

    @model_validator(mode="after")
    def _comment_matches_mode(self) -> Self:
        if (self.mode in COMMENT_MODES) != (self.comment is not None):
            raise ValueError(COMMENT_NEEDED)
        return self


class ImproveStoryResponse(ResponseEnvelope):
    """What the backend receives: a proposal, never a stored fact."""

    model_config = ConfigDict(extra="forbid")

    improved_description: str = Field(
        description="The rewritten description; for polish_comment the comment, for reply the reply"
    )
    acceptance_criteria: str | None
    rationale: str
    changed: bool
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
