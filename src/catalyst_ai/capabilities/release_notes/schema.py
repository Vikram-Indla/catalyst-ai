"""The shape the model's text must validate against before anything else happens to it."""

from pydantic import BaseModel, ConfigDict, Field

MAX_ENTRY_CHARS = 1_000
MAX_SUMMARY_CHARS = 12_000
MAX_ENTRIES = 200
MAX_RATIONALE_CHARS = 500


class ModelEntry(BaseModel):
    """One line the model wrote, with the change id it cites."""

    model_config = ConfigDict(extra="forbid")

    source_id: str
    text: str = Field(max_length=MAX_ENTRY_CHARS)


class ModelSection(BaseModel):
    """One kind's entries as the model grouped them."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    entries: list[ModelEntry] = Field(max_length=MAX_ENTRIES)


class ModelOutput(BaseModel):
    """What a valid completion carries; anything else is `ai.output.invalid`."""

    model_config = ConfigDict(extra="forbid")

    sections: list[ModelSection] = Field(default_factory=list, max_length=MAX_ENTRIES)
    highlights: list[ModelEntry] = Field(default_factory=list, max_length=MAX_ENTRIES)
    summary: str = Field(default="", max_length=MAX_SUMMARY_CHARS)
    attention: list[ModelEntry] = Field(default_factory=list, max_length=MAX_ENTRIES)
    empty_reason: str | None = None
    rationale: str = Field(min_length=1, max_length=MAX_RATIONALE_CHARS)


def prose_of(output: ModelOutput) -> str:
    """Return every free-text field of a completion, joined for the leakage scan."""
    lines = [e.text for s in output.sections for e in s.entries]
    lines += [e.text for e in output.highlights] + [e.text for e in output.attention]
    return "\n".join([output.summary, *lines])


def output_schema() -> dict[str, object]:
    """Return the JSON schema handed to the provider's structured-output feature."""
    return ModelOutput.model_json_schema()
