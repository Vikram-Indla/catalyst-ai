"""The shape the model's text must validate against before anything else happens to it."""

from pydantic import BaseModel, ConfigDict, Field

MAX_LINE_CHARS = 1_000
MAX_SUMMARY_CHARS = 12_000
MAX_LIST = 60
MAX_RATIONALE_CHARS = 500


class ModelFact(BaseModel):
    """One restated timeline entry, with the id it cites."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    text: str = Field(max_length=MAX_LINE_CHARS)


class ModelFactor(BaseModel):
    """One contributing factor with the entry ids it rests on."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=MAX_LINE_CHARS)
    evidence: list[str] = Field(default_factory=list, max_length=MAX_LIST)


class ModelAction(BaseModel):
    """One proposed action with its evidence and the model's own confidence."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=MAX_LINE_CHARS)
    evidence: list[str] = Field(default_factory=list, max_length=MAX_LIST)
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)


class ModelOutput(BaseModel):
    """What a valid completion carries; anything else is `ai.output.invalid`."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(default="", max_length=MAX_SUMMARY_CHARS)
    facts: list[ModelFact] = Field(default_factory=list, max_length=MAX_LIST)
    contributing_factors: list[ModelFactor] = Field(default_factory=list, max_length=MAX_LIST)
    action_items: list[ModelAction] = Field(default_factory=list, max_length=MAX_LIST)
    participants_mentioned: list[str] = Field(default_factory=list, max_length=MAX_LIST)
    empty_reason: str | None = None
    rationale: str = Field(min_length=1, max_length=MAX_RATIONALE_CHARS)


def prose_of(output: ModelOutput) -> str:
    """Return every free-text field of a completion, joined for the scans."""
    lines = [f.text for f in output.facts] + [f.text for f in output.contributing_factors]
    return "\n".join([output.summary, *lines, *(a.text for a in output.action_items)])


def output_schema() -> dict[str, object]:
    """Return the JSON schema handed to the provider's structured-output feature."""
    return ModelOutput.model_json_schema()
