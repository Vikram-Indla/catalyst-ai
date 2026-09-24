"""The brief operation: an executive briefing over the strategy chain the backend sends.

The backend owns the chain — a theme, its objectives with their official status and progress, the
key results with their official values and targets, the linked projects with their delivery and
strategic health kept as two fields, and the open findings — and sends it typed. The service
reads nothing else. Every sentence of the answer cites the chain ids it rests on, states no
number the chain does not carry, keeps delivery health and strategic health apart, and says
"not measured" where the chain has no value, never zero.
"""

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from catalyst_ai.contract.envelopes import RequestEnvelope, ResponseEnvelope, classified

MAX_ID = 64
MAX_TITLE = 300
MAX_CHARTER = 2_000
MAX_FINDING = 1_000
MAX_OKRS = 20
MAX_KEY_RESULTS = 20
MAX_PROJECTS = 50
MAX_FINDINGS = 50
MAX_UNIT = 16
MAX_SENTENCE = 600
MAX_ITEMS = 10
MIN_SENTENCES = 3
MAX_SENTENCES = 5
ID_SHAPE = r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$"

Health = Literal["on_track", "at_risk", "off_track", "not_measured"]
Severity = Literal["low", "medium", "high"]
EmptyReason = Literal["nothing_to_brief"]


class KeyResult(BaseModel):
    """A key result with its official value and target; a null value is "not measured"."""

    model_config = ConfigDict(extra="forbid")

    id: Annotated[
        str,
        Field(
            pattern=ID_SHAPE,
            json_schema_extra=classified("INTERNAL", "The key result's id; cited by the answer"),
        ),
    ]
    title: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_TITLE,
            json_schema_extra=classified("CONFIDENTIAL", "Its title"),
        ),
    ]
    value: Annotated[
        float | None,
        Field(json_schema_extra=classified("INTERNAL", "The official value; null is not measured")),
    ] = None
    target: Annotated[
        float | None, Field(json_schema_extra=classified("INTERNAL", "The official target"))
    ] = None
    unit: Annotated[
        str | None,
        Field(max_length=MAX_UNIT, json_schema_extra=classified("INTERNAL", "The unit, as shown")),
    ] = None
    as_of: Annotated[
        date | None, Field(json_schema_extra=classified("INTERNAL", "When the value was taken"))
    ] = None


class Objective(BaseModel):
    """An objective with its official status and progress, and its key results."""

    model_config = ConfigDict(extra="forbid")

    id: Annotated[
        str,
        Field(
            pattern=ID_SHAPE,
            json_schema_extra=classified("INTERNAL", "The objective's id; cited by the answer"),
        ),
    ]
    title: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_TITLE,
            json_schema_extra=classified("CONFIDENTIAL", "Its title"),
        ),
    ]
    status: Annotated[Health, Field(json_schema_extra=classified("INTERNAL", "Official status"))]
    progress: Annotated[
        float | None,
        Field(
            ge=0,
            le=100,
            json_schema_extra=classified(
                "INTERNAL", "Official progress in percent; null is not measured"
            ),
        ),
    ] = None
    key_results: Annotated[
        list[KeyResult],
        Field(
            max_length=MAX_KEY_RESULTS, json_schema_extra=classified("INTERNAL", "Its key results")
        ),
    ] = []


class ProjectCard(BaseModel):
    """A linked project: delivery health and strategic health are two facts, never one."""

    model_config = ConfigDict(extra="forbid")

    id: Annotated[
        str,
        Field(
            pattern=ID_SHAPE,
            json_schema_extra=classified("INTERNAL", "The project's id; cited by the answer"),
        ),
    ]
    title: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_TITLE,
            json_schema_extra=classified("CONFIDENTIAL", "Its title"),
        ),
    ]
    delivery_health: Annotated[
        Health, Field(json_schema_extra=classified("INTERNAL", "Schedule and scope health"))
    ]
    strategic_health: Annotated[
        Health, Field(json_schema_extra=classified("INTERNAL", "Contribution to the objectives"))
    ]
    blocked: Annotated[
        bool, Field(json_schema_extra=classified("INTERNAL", "Whether the project is blocked"))
    ] = False


class Finding(BaseModel):
    """An open finding against the theme."""

    model_config = ConfigDict(extra="forbid")

    id: Annotated[
        str,
        Field(
            pattern=ID_SHAPE,
            json_schema_extra=classified("INTERNAL", "The finding's id; cited by the answer"),
        ),
    ]
    text: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_FINDING,
            json_schema_extra=classified("CONFIDENTIAL", "The finding"),
        ),
    ]
    severity: Annotated[Severity, Field(json_schema_extra=classified("INTERNAL", "Its severity"))]


class Theme(BaseModel):
    """The theme the chain hangs from, with its charter summary."""

    model_config = ConfigDict(extra="forbid")

    id: Annotated[
        str,
        Field(
            pattern=ID_SHAPE,
            json_schema_extra=classified("INTERNAL", "The theme's id; cited by the answer"),
        ),
    ]
    title: Annotated[
        str,
        Field(
            min_length=1,
            max_length=MAX_TITLE,
            json_schema_extra=classified("CONFIDENTIAL", "Its title"),
        ),
    ]
    charter_summary: Annotated[
        str,
        Field(
            max_length=MAX_CHARTER,
            json_schema_extra=classified("CONFIDENTIAL", "The charter, summarised"),
        ),
    ] = ""


class Chain(BaseModel):
    """The strategy chain, as the backend owns it."""

    model_config = ConfigDict(extra="forbid")

    theme: Theme
    objectives: list[Objective] = Field(default=[], max_length=MAX_OKRS)
    projects: list[ProjectCard] = Field(default=[], max_length=MAX_PROJECTS)
    findings: list[Finding] = Field(default=[], max_length=MAX_FINDINGS)


class BriefRequest(RequestEnvelope):
    """What the backend sends: the chain, the language, the audience and the length."""

    model_config = ConfigDict(extra="forbid")

    chain: Annotated[
        Chain, Field(json_schema_extra=classified("CONFIDENTIAL", "The strategy chain"))
    ]
    locale: Annotated[
        Literal["en", "ar"],
        Field(json_schema_extra=classified("PUBLIC", "The briefing's language")),
    ] = "en"
    audience: Annotated[
        Literal["executive"],
        Field(json_schema_extra=classified("PUBLIC", "Who reads the briefing")),
    ] = "executive"
    max_sentences: Annotated[
        int,
        Field(
            ge=MIN_SENTENCES,
            le=MAX_SENTENCES,
            json_schema_extra=classified("PUBLIC", "The summary's length in sentences"),
        ),
    ] = MAX_SENTENCES


class CitedSentence(BaseModel):
    """One sentence and the chain ids it rests on."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1, max_length=MAX_SENTENCE)
    cites: list[str] = Field(min_length=1)


class BriefResponse(ResponseEnvelope):
    """A proposal to read, never a stored fact: every sentence cites the chain."""

    model_config = ConfigDict(extra="forbid")

    summary: list[CitedSentence] = Field(max_length=MAX_SENTENCES)
    highlights: list[CitedSentence] = Field(max_length=MAX_ITEMS)
    risks: list[CitedSentence] = Field(max_length=MAX_ITEMS)
    asks: list[CitedSentence] = Field(max_length=MAX_ITEMS)
    unsupported: list[str] = Field(max_length=MAX_ITEMS)
    empty_reason: EmptyReason | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)
