"""The generate_tests operation: test cases from criteria, or a plan and tables from cases."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from catalyst_ai.contract.envelopes import RequestEnvelope, ResponseEnvelope, classified

MAX_CRITERIA = 50
MAX_CASES = 50
MAX_STEPS = 12
MAX_ID = 64
MAX_KEY = 32
MAX_TITLE = 500
MAX_TEXT = 8_000
MAX_LINE = 600
MAX_LINES = 20
MAX_TABLES = 10
MAX_COLUMNS = 8
MAX_ROWS = 20
MAX_LANGUAGE = 16
MIN_MAX_CASES = 1
MAX_MAX_CASES = 20
DEFAULT_MAX_CASES = 10
LANGUAGE_PATTERN = r"^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$"

EmptyReason = Literal["nothing_to_test"]


class GenerateTestsMode(StrEnum):
    """`cases` writes test cases from a story; `artefacts` a plan and data tables from cases."""

    CASES = "cases"
    ARTEFACTS = "artefacts"


class Priority(StrEnum):
    """How urgent a case is to run."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Area(StrEnum):
    """What a case covers."""

    HAPPY = "happy"
    NEGATIVE = "negative"
    BOUNDARY = "boundary"
    SECURITY = "security"
    PERFORMANCE = "performance"
    INTEGRATION = "integration"


class Story(BaseModel):
    """The story under test."""

    model_config = ConfigDict(extra="forbid")

    key: str | None = Field(default=None, max_length=MAX_KEY)
    title: str = Field(min_length=1, max_length=MAX_TITLE)
    description: str | None = Field(default=None, max_length=MAX_TEXT)


class Criterion(BaseModel):
    """One acceptance criterion with the id a case cites."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=MAX_ID)
    text: str = Field(min_length=1, max_length=MAX_LINE)


class Step(BaseModel):
    """One step of an existing case."""

    model_config = ConfigDict(extra="forbid")

    action: str = Field(min_length=1, max_length=MAX_LINE)
    expected: str = Field(min_length=1, max_length=MAX_LINE)


class ExistingCase(BaseModel):
    """One test case the artefacts are built from, with the id a table cites."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=MAX_ID)
    title: str = Field(min_length=1, max_length=MAX_TITLE)
    objective: str | None = Field(default=None, max_length=MAX_LINE)
    steps: list[Step] = Field(default_factory=list, max_length=MAX_STEPS)


class GenerateTestsRequest(RequestEnvelope):
    """The story and its criteria for `cases`; the cases for `artefacts`."""

    model_config = ConfigDict(extra="forbid")

    mode: Annotated[
        GenerateTestsMode,
        Field(
            json_schema_extra=classified("PUBLIC", "Cases from criteria, or artefacts from cases")
        ),
    ]
    story: Annotated[
        Story,
        Field(json_schema_extra=classified("CONFIDENTIAL", "The story under test")),
    ]
    criteria: Annotated[
        list[Criterion],
        Field(
            max_length=MAX_CRITERIA,
            json_schema_extra=classified(
                "CONFIDENTIAL", "The acceptance criteria with the ids a case must cite"
            ),
        ),
    ] = Field(default_factory=list)
    cases: Annotated[
        list[ExistingCase],
        Field(
            max_length=MAX_CASES,
            json_schema_extra=classified(
                "CONFIDENTIAL", "The cases the artefacts are built from, with ids"
            ),
        ),
    ] = Field(default_factory=list)
    max_cases: Annotated[
        int,
        Field(
            ge=MIN_MAX_CASES,
            le=MAX_MAX_CASES,
            json_schema_extra=classified("PUBLIC", "The most cases wanted"),
        ),
    ] = DEFAULT_MAX_CASES
    language: Annotated[
        str | None,
        Field(
            max_length=MAX_LANGUAGE,
            pattern=LANGUAGE_PATTERN,
            json_schema_extra=classified("PUBLIC", "BCP 47 tag; absent preserves the story's"),
        ),
    ] = None


class TestCase(BaseModel):
    """One case: given, when, then; what it covers, or `inferred` when nothing stated does."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1, max_length=MAX_TITLE)
    given: str = Field(min_length=1, max_length=MAX_LINE)
    when: str = Field(min_length=1, max_length=MAX_LINE)
    then: str = Field(min_length=1, max_length=MAX_LINE)
    priority: Priority
    area: Area
    covers: list[str] = Field(max_length=MAX_CRITERIA)
    inferred: bool = False


class OutlineSection(BaseModel):
    """One section of the plan outline, traced to the cases it draws on."""

    model_config = ConfigDict(extra="forbid")

    heading: str = Field(min_length=1, max_length=MAX_TITLE)
    lines: list[str] = Field(max_length=MAX_LINES)
    covers: list[str] = Field(max_length=MAX_CASES)


class DataTable(BaseModel):
    """One table of test data, traced to the cases that use it."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=MAX_TITLE)
    columns: list[str] = Field(min_length=1, max_length=MAX_COLUMNS)
    rows: list[list[str]] = Field(max_length=MAX_ROWS)
    covers: list[str] = Field(min_length=1, max_length=MAX_CASES)


class GenerateTestsResponse(ResponseEnvelope):
    """The cases and the criteria left uncovered, or the outline and the tables; every id traced."""

    model_config = ConfigDict(extra="forbid")

    cases: list[TestCase]
    gaps: list[str]
    outline: list[OutlineSection]
    data_tables: list[DataTable]
    empty_reason: EmptyReason | None
    confidence: float = Field(ge=0.0, le=1.0)
