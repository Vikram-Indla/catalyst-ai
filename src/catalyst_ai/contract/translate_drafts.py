"""The translation drafts job: many fields of seeded records into Arabic drafts, never reviewed.

The backend sends a batch of `{record_ref, field, en}` items and the glossary with its version, as a
job. Each item comes back as a draft whose status is `machine_draft` and nothing else: only the
backend's linguistic review may promote it, and the service has no other status to give. An item
is keyed by its record, its field, the hash of its text and the glossary version; the same key is
answered once, so resubmitting a batch drafts only what was not drafted. An empty field is skipped
and reported. When the tenant's budget, the provider or the job's time runs out, the items not
reached come back as `remaining`, to be resubmitted; nothing is half-drafted.
"""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from catalyst_ai.contract.envelopes import RequestEnvelope, ResponseEnvelope, classified
from catalyst_ai.contract.translate import MAX_GLOSSARY, MAX_OUTPUT_CHARS, MAX_TEXT, GlossaryEntry

MAX_ITEMS = 200
MAX_REF = 200
MAX_VERSION = 64
FIELD_PATTERN = r"^[a-z][A-Za-z0-9_]{0,63}$"
KEY_PATTERN = r"^[0-9a-f]{64}$"

DraftStatus = Literal["machine_draft"]
MACHINE_DRAFT: DraftStatus = "machine_draft"
SkipReason = Literal["empty", "refused"]
RemainingReason = Literal["budget_exhausted", "provider_unavailable", "time_exhausted"]


class DraftItem(BaseModel):
    """One field of one record, in English, as the backend holds it."""

    model_config = ConfigDict(extra="forbid")

    record_ref: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_REF,
            json_schema_extra=classified("INTERNAL", "The backend's reference to the record"),
        ),
    ]
    field: Annotated[
        str,
        Field(
            pattern=FIELD_PATTERN,
            json_schema_extra=classified("INTERNAL", "Which field of the record: name, charter …"),
        ),
    ]
    en: Annotated[
        str,
        Field(
            max_length=MAX_TEXT,
            json_schema_extra=classified("CONFIDENTIAL", "The field's English text; may be empty"),
        ),
    ]


class DraftsRequest(RequestEnvelope):
    """A batch of fields and the glossary they are drafted under."""

    model_config = ConfigDict(extra="forbid")

    items: Annotated[
        list[DraftItem],
        Field(
            min_length=1,
            max_length=MAX_ITEMS,
            json_schema_extra=classified("CONFIDENTIAL", "The fields to draft"),
        ),
    ]
    glossary: Annotated[
        list[GlossaryEntry],
        Field(
            max_length=MAX_GLOSSARY,
            json_schema_extra=classified("INTERNAL", "Governed English → Arabic terms"),
        ),
    ] = Field(default_factory=list)
    glossary_version: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_VERSION,
            json_schema_extra=classified(
                "INTERNAL", "The glossary's version; part of every item's key"
            ),
        ),
    ]


class Draft(BaseModel):
    """One Arabic draft: never reviewed, whatever its quality."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(pattern=KEY_PATTERN)
    record_ref: str
    field: str
    ar: str = Field(max_length=MAX_OUTPUT_CHARS)
    status: DraftStatus = MACHINE_DRAFT
    glossary_hits: list[str] = Field(default_factory=list)
    unresolved: list[str] = Field(default_factory=list)


class Skipped(BaseModel):
    """An item not drafted, and why: an empty field, or a text the service refused."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(pattern=KEY_PATTERN)
    record_ref: str
    field: str
    reason: SkipReason
    code: str | None = None


class Remaining(BaseModel):
    """An item not reached in this run; resubmitted, it is drafted then."""

    model_config = ConfigDict(extra="forbid")

    key: str = Field(pattern=KEY_PATTERN)
    record_ref: str
    field: str
    reason: RemainingReason


class DraftProgress(BaseModel):
    """The counts a seeding run reports: every item is in exactly one of the three."""

    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    drafted: int = Field(ge=0)
    skipped: int = Field(ge=0)
    remaining: int = Field(ge=0)
    from_cache: int = Field(ge=0)


class DraftsResponse(ResponseEnvelope):
    """The drafts, the skipped and the remaining items, and the counts."""

    model_config = ConfigDict(extra="forbid")

    drafts: list[Draft]
    skipped: list[Skipped]
    remaining: list[Remaining]
    progress: DraftProgress
