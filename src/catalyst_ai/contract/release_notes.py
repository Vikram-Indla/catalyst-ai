"""The release_notes operation: notes or an overview from a change list, every entry traced."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from catalyst_ai.contract.envelopes import RequestEnvelope, ResponseEnvelope, classified

MAX_CHANGES = 200
MAX_ID = 64
MAX_KEY = 32
MAX_KIND = 64
MAX_TITLE = 500
MAX_TEXT = 4_000
MAX_NAME = 200
MAX_VERSION = 64
MAX_STATUS = 64
MAX_ENTRY = 600
MAX_ENTRIES = 200
MAX_SUMMARY = 8_000
MAX_LANGUAGE = 16
KIND_SHAPE = r"^[a-z][a-z0-9_]{0,63}$"
PARTICIPANT_SHAPE = r"^p[0-9]{1,4}$"
LANGUAGE_PATTERN = r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$"

EmptyReason = Literal["nothing_to_report"]


class ReleaseNotesMode(StrEnum):
    """`notes` writes the notes themselves; `summary` an overview for a lead."""

    NOTES = "notes"
    SUMMARY = "summary"


class Audience(StrEnum):
    """Who reads the notes: the team, or the customers of the product."""

    INTERNAL = "internal"
    CUSTOMER = "customer"


class StatusCategory(StrEnum):
    """Where a change stands, in the three categories the engine knows."""

    TODO = "todo"
    IN_PROGRESS = "in_progress"
    DONE = "done"


class Release(BaseModel):
    """The release as the backend describes it; nothing here is a person."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=MAX_NAME)
    version: str | None = Field(default=None, max_length=MAX_VERSION)
    target_date: str | None = Field(default=None, max_length=MAX_KEY)
    status: str | None = Field(default=None, max_length=MAX_STATUS)
    description: str | None = Field(default=None, max_length=MAX_TEXT)


class Change(BaseModel):
    """One change in the release: the id every note must cite, its kind, its text, its state."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=MAX_ID)
    key: str | None = Field(default=None, max_length=MAX_KEY)
    kind: str = Field(pattern=KIND_SHAPE, max_length=MAX_KIND)
    title: str = Field(min_length=1, max_length=MAX_TITLE)
    description: str | None = Field(default=None, max_length=MAX_TEXT)
    status_category: StatusCategory = StatusCategory.DONE
    participant: str | None = Field(default=None, pattern=PARTICIPANT_SHAPE)


class ReleaseNotesRequest(RequestEnvelope):
    """The release, its changes with ids, the mode and the audience."""

    model_config = ConfigDict(extra="forbid")

    mode: Annotated[
        ReleaseNotesMode,
        Field(json_schema_extra=classified("PUBLIC", "Notes, or an overview for a lead")),
    ]
    release: Annotated[
        Release,
        Field(json_schema_extra=classified("INTERNAL", "Name, version, date, status, description")),
    ]
    changes: Annotated[
        list[Change],
        Field(
            max_length=MAX_CHANGES,
            json_schema_extra=classified(
                "CONFIDENTIAL", "The changes with the ids every entry must cite"
            ),
        ),
    ]
    audience: Annotated[
        Audience,
        Field(json_schema_extra=classified("PUBLIC", "Internal wording, or customer-facing")),
    ] = Audience.INTERNAL
    language: Annotated[
        str | None,
        Field(
            max_length=MAX_LANGUAGE,
            pattern=LANGUAGE_PATTERN,
            json_schema_extra=classified("PUBLIC", "BCP 47 tag; absent preserves the changes'"),
        ),
    ] = None


class Entry(BaseModel):
    """One line of the notes, traced to the change it came from."""

    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1, max_length=MAX_ID)
    text: str = Field(min_length=1, max_length=MAX_ENTRY)


class Section(BaseModel):
    """The entries of one kind, in the order the changes came."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    entries: list[Entry] = Field(max_length=MAX_ENTRIES)


class ReleaseNotesResponse(ResponseEnvelope):
    """Notes as sections and highlights, or an overview; what is not done; every id traced."""

    model_config = ConfigDict(extra="forbid")

    sections: list[Section]
    highlights: list[Entry]
    summary: str = Field(max_length=MAX_SUMMARY)
    attention: list[Entry]
    in_flight: list[str]
    empty_reason: EmptyReason | None
    confidence: float = Field(ge=0.0, le=1.0)
