"""The shape the model's text must validate against before anything else happens to it."""

from pydantic import BaseModel, ConfigDict, Field

MAX_SUMMARY_CHARS = 12_000
MAX_RATIONALE_CHARS = 500
MAX_MENTIONED = 50


class ModelOutput(BaseModel):
    """What a valid completion carries; anything else is `ai.output.invalid`."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(max_length=MAX_SUMMARY_CHARS)
    participants_mentioned: list[str] = Field(max_length=MAX_MENTIONED)
    empty_reason: str | None = None
    rationale: str = Field(min_length=1, max_length=MAX_RATIONALE_CHARS)


def output_schema() -> dict[str, object]:
    """Return the JSON schema handed to the provider's structured-output feature."""
    return ModelOutput.model_json_schema()
