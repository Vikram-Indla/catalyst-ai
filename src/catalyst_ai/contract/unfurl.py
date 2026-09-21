"""The unfurl operation: a supplied item or page becomes a card; nothing is fetched.

The backend sends the content it already holds; the card says only what that content says.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from catalyst_ai.contract.envelopes import RequestEnvelope, ResponseEnvelope, classified

MAX_ID = 64
MAX_TITLE = 500
MAX_TEXT = 20_000
MAX_STATUS = 64
MAX_SUMMARY = 300
MAX_FACTS = 6
MAX_FACT_LABEL = 40
MAX_FACT_VALUE = 120
MAX_LANGUAGE = 16
ID_SHAPE = r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,63}$"
LANGUAGE_PATTERN = r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$"

UnfurlKind = Literal["item", "page"]


class UnfurlRequest(RequestEnvelope):
    """What the backend holds about the thing a member linked."""

    model_config = ConfigDict(extra="forbid")

    kind: Annotated[
        UnfurlKind, Field(json_schema_extra=classified("PUBLIC", "A work item or a page"))
    ]
    id: Annotated[
        str,
        Field(pattern=ID_SHAPE, json_schema_extra=classified("INTERNAL", "The backend's id")),
    ]
    title: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_TITLE,
            json_schema_extra=classified("CONFIDENTIAL", "The title as stored"),
        ),
    ]
    text: Annotated[
        str | None,
        Field(
            max_length=MAX_TEXT,
            json_schema_extra=classified("CONFIDENTIAL", "The description or the page's text"),
        ),
    ] = None
    status: Annotated[
        str | None,
        Field(max_length=MAX_STATUS, json_schema_extra=classified("INTERNAL", "An item's status")),
    ] = None
    language: Annotated[
        str | None,
        Field(
            max_length=MAX_LANGUAGE,
            pattern=LANGUAGE_PATTERN,
            json_schema_extra=classified("PUBLIC", "BCP 47 tag of the card; else the text's"),
        ),
    ] = None


class Fact(BaseModel):
    """One labelled value the card shows, taken from the supplied text."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=MAX_FACT_LABEL)
    value: str = Field(min_length=1, max_length=MAX_FACT_VALUE)


class UnfurlResponse(ResponseEnvelope):
    """The card: the title echoed, a one-line summary, a few facts — nothing not in the input."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(max_length=MAX_TITLE)
    summary: str = Field(max_length=MAX_SUMMARY)
    facts: list[Fact] = Field(max_length=MAX_FACTS)
    confidence: float = Field(ge=0.0, le=1.0)
