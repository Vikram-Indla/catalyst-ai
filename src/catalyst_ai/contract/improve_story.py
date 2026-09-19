"""The improve-story operation: a rewrite of a work item's text under one editorial mode."""

from enum import StrEnum
from typing import Annotated

from pydantic import ConfigDict, Field

from catalyst_ai.contract.envelopes import RequestEnvelope, ResponseEnvelope, classified

MAX_TITLE = 500
MAX_TEXT = 20_000
MAX_CRITERIA = 10_000
MAX_HINT = 500
MAX_TYPE = 64
MAX_LANGUAGE = 16


class ImproveStoryMode(StrEnum):
    """The editorial operations; each maps to one instruction block of the prompt."""

    CLARIFY = "clarify"
    EXPAND = "expand"
    ACCEPTANCE_CRITERIA = "acceptance_criteria"
    USER_STORY = "user_story"
    SHORTEN = "shorten"
    EDGE_CASES = "edge_cases"


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


class ImproveStoryResponse(ResponseEnvelope):
    """What the backend receives: a proposal, never a stored fact."""

    model_config = ConfigDict(extra="forbid")

    improved_description: str
    acceptance_criteria: str | None
    rationale: str
    changed: bool
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
