"""The shape the model's text must validate against before anything else happens to it."""

from pydantic import BaseModel, ConfigDict, Field

from catalyst_ai.contract.generate_tests import Area, Priority

MAX_LINE_CHARS = 1_000
MAX_LIST = 50
MAX_RATIONALE_CHARS = 500


class ModelCase(BaseModel):
    """One case as the model wrote it."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(max_length=MAX_LINE_CHARS)
    given: str = Field(max_length=MAX_LINE_CHARS)
    when: str = Field(max_length=MAX_LINE_CHARS)
    then: str = Field(max_length=MAX_LINE_CHARS)
    priority: Priority
    area: Area
    covers: list[str] = Field(default_factory=list, max_length=MAX_LIST)
    inferred: bool = False


class ModelSection(BaseModel):
    """One outline section as the model wrote it."""

    model_config = ConfigDict(extra="forbid")

    heading: str = Field(max_length=MAX_LINE_CHARS)
    lines: list[str] = Field(default_factory=list, max_length=MAX_LIST)
    covers: list[str] = Field(default_factory=list, max_length=MAX_LIST)


class ModelTable(BaseModel):
    """One data table as the model wrote it."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(max_length=MAX_LINE_CHARS)
    columns: list[str] = Field(max_length=MAX_LIST)
    rows: list[list[str]] = Field(default_factory=list, max_length=MAX_LIST)
    covers: list[str] = Field(default_factory=list, max_length=MAX_LIST)


class ModelOutput(BaseModel):
    """What a valid completion carries; anything else is `ai.output.invalid`."""

    model_config = ConfigDict(extra="forbid")

    cases: list[ModelCase] = Field(default_factory=list, max_length=MAX_LIST)
    gaps: list[str] = Field(default_factory=list, max_length=MAX_LIST)
    outline: list[ModelSection] = Field(default_factory=list, max_length=MAX_LIST)
    data_tables: list[ModelTable] = Field(default_factory=list, max_length=MAX_LIST)
    empty_reason: str | None = None
    rationale: str = Field(min_length=1, max_length=MAX_RATIONALE_CHARS)


def prose_of(output: ModelOutput) -> str:
    """Return every free-text field of a completion, joined for the leakage scan."""
    cases = [f"{c.title}\n{c.given}\n{c.when}\n{c.then}" for c in output.cases]
    outline = [s.heading + "\n" + "\n".join(s.lines) for s in output.outline]
    tables = [
        t.name + "\n" + "\n".join(" ".join(row) for row in t.rows) for t in output.data_tables
    ]
    return "\n".join(cases + outline + tables)


def output_schema() -> dict[str, object]:
    """Return the JSON schema handed to the provider's structured-output feature."""
    return ModelOutput.model_json_schema()
