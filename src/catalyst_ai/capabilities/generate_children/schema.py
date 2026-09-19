"""The shape the model's text must validate against; the hierarchy is checked after."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from catalyst_ai.contract.generate_children import MAX_ITEMS, MAX_LEVEL_NAME, MAX_TEXT, MAX_TITLE

MAX_CRITERIA = 20
MAX_CRITERION = 1_000


class ModelCandidate(BaseModel):
    """One candidate as the model writes it."""

    model_config = ConfigDict(extra="forbid")

    type: str = Field(min_length=1, max_length=MAX_LEVEL_NAME)
    title: str = Field(min_length=1, max_length=MAX_TITLE)
    description: str = Field(max_length=MAX_TEXT)
    acceptance_criteria: list[str] = Field(default_factory=list, max_length=MAX_CRITERIA)
    duplicate_of: str | None = Field(default=None, max_length=MAX_TITLE)


class ModelOutput(BaseModel):
    """Candidates or an empty list with a reason; anything else is `ai.output.invalid`."""

    model_config = ConfigDict(extra="forbid")

    candidates: list[ModelCandidate] = Field(max_length=MAX_ITEMS)
    empty_reason: (
        Literal["parent_too_vague", "siblings_cover_it", "nothing_at_this_level"] | None
    ) = None
    rationale: str = Field(min_length=1, max_length=MAX_CRITERION)


def output_schema() -> dict[str, object]:
    """Return the JSON schema handed to the provider's structured-output feature."""
    return ModelOutput.model_json_schema()
