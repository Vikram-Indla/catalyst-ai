"""The shape the model's text must validate against before anything else happens to it."""

from pydantic import BaseModel, ConfigDict, Field

from catalyst_ai.contract.propose_workflow import (
    MAX_STATUSES,
    MAX_TRANSITIONS,
    StatusBase,
    TransitionBase,
)

MAX_RATIONALE_CHARS = 500


class ModelOutput(BaseModel):
    """What a valid completion carries; anything else is `ai.output.invalid`."""

    model_config = ConfigDict(extra="forbid")

    statuses: list[StatusBase] = Field(max_length=MAX_STATUSES)
    transitions: list[TransitionBase] = Field(max_length=MAX_TRANSITIONS)
    empty_reason: str | None = None
    rationale: str = Field(min_length=1, max_length=MAX_RATIONALE_CHARS)


def output_schema() -> dict[str, object]:
    """Return the JSON schema handed to the provider's structured-output feature."""
    return ModelOutput.model_json_schema()
