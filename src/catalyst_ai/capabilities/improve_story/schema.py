"""The shape the model's text must validate against before anything else happens to it."""

from pydantic import BaseModel, ConfigDict, Field

MAX_OUTPUT_CHARS = 40_000
MAX_RATIONALE_CHARS = 1_000


class ModelOutput(BaseModel):
    """What a valid completion carries; anything else is `ai.output.invalid`."""

    model_config = ConfigDict(extra="forbid")

    description: str = Field(max_length=MAX_OUTPUT_CHARS)
    acceptance_criteria: str | None = Field(default=None, max_length=MAX_OUTPUT_CHARS)
    rationale: str = Field(min_length=1, max_length=MAX_RATIONALE_CHARS)
    changed: bool


def output_schema() -> dict[str, object]:
    """Return the JSON schema handed to the provider's structured-output feature."""
    return ModelOutput.model_json_schema()
