"""The shape the model's text must validate against before the grammar reads its query."""

from pydantic import BaseModel, ConfigDict, Field

from catalyst_ai.contract.interpret_query import (
    MAX_EXPLANATION,
    MAX_QUERY,
    MAX_UNRESOLVED,
    MAX_VALUE,
)

MAX_RATIONALE_CHARS = 300


class ModelOutput(BaseModel):
    """What a valid completion carries; anything else is `ai.output.invalid`."""

    model_config = ConfigDict(extra="forbid")

    query: str = Field(max_length=MAX_QUERY)
    explanation: str = Field(min_length=1, max_length=MAX_EXPLANATION)
    unresolved: list[str] = Field(default_factory=list, max_length=MAX_UNRESOLVED)
    rationale: str = Field(min_length=1, max_length=MAX_RATIONALE_CHARS)

    def terms(self) -> list[str]:
        """Return the unresolved terms, trimmed and bounded."""
        return [term.strip()[:MAX_VALUE] for term in self.unresolved if term.strip()]


def output_schema() -> dict[str, object]:
    """Return the JSON schema handed to the provider's structured-output feature."""
    return ModelOutput.model_json_schema()
