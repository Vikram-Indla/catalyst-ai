"""The post_mortem operation: a blameless draft from a timeline — facts traced, analysis apart."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from catalyst_ai.contract.envelopes import RequestEnvelope, ResponseEnvelope, classified

MAX_EVENTS = 200
MAX_ID = 64
MAX_KEY = 32
MAX_TITLE = 500
MAX_TEXT = 4_000
MAX_SEVERITY = 32
MAX_LINE = 600
MAX_LINES = 30
MAX_SUMMARY = 8_000
MAX_LANGUAGE = 16
PARTICIPANT_SHAPE = r"^p[0-9]{1,4}$"
LANGUAGE_PATTERN = r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$"

EmptyReason = Literal["timeline_empty"]


class Incident(BaseModel):
    """The incident as the backend describes it; nothing here is a person."""

    model_config = ConfigDict(extra="forbid")

    key: str | None = Field(default=None, max_length=MAX_KEY)
    title: str = Field(min_length=1, max_length=MAX_TITLE)
    severity: str | None = Field(default=None, max_length=MAX_SEVERITY)
    started_at: datetime | None = None
    resolved_at: datetime | None = None
    impact: str | None = Field(default=None, max_length=MAX_TEXT)


class Event(BaseModel):
    """One timeline entry: the id a fact must cite, when, who (a token), what."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=MAX_ID)
    at: datetime
    participant: str | None = Field(default=None, pattern=PARTICIPANT_SHAPE)
    text: str = Field(min_length=1, max_length=MAX_TEXT)


class PostMortemRequest(RequestEnvelope):
    """The incident and its timeline, oldest first, people as tokens."""

    model_config = ConfigDict(extra="forbid")

    incident: Annotated[
        Incident,
        Field(
            json_schema_extra=classified(
                "CONFIDENTIAL", "Key, title, severity, the span, the impact as recorded"
            )
        ),
    ]
    timeline: Annotated[
        list[Event],
        Field(
            max_length=MAX_EVENTS,
            json_schema_extra=classified(
                "CONFIDENTIAL", "The entries with the ids every fact must cite; people as tokens"
            ),
        ),
    ]
    language: Annotated[
        str | None,
        Field(
            max_length=MAX_LANGUAGE,
            pattern=LANGUAGE_PATTERN,
            json_schema_extra=classified("PUBLIC", "BCP 47 tag; absent preserves the timeline's"),
        ),
    ] = None


class Fact(BaseModel):
    """One line of the reconstructed timeline, traced to the entry it restates."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1, max_length=MAX_ID)
    text: str = Field(min_length=1, max_length=MAX_LINE)


class Factor(BaseModel):
    """One contributing factor — analysis — with the entries it rests on."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_LINE)
    evidence: list[str] = Field(min_length=1, max_length=MAX_LINES)


class ActionItem(BaseModel):
    """One proposed action, a candidate the backend may turn into work, with its evidence."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_LINE)
    evidence: list[str] = Field(max_length=MAX_LINES)
    confidence: float = Field(ge=0.0, le=1.0)


class PostMortemResponse(ResponseEnvelope):
    """The summary, the facts, the factors, the candidate actions; the tokens named."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(max_length=MAX_SUMMARY)
    facts: list[Fact]
    contributing_factors: list[Factor]
    action_items: list[ActionItem]
    participants_mentioned: list[str]
    empty_reason: EmptyReason | None
    confidence: float = Field(ge=0.0, le=1.0)
