"""The shape the model's text must validate against before anything else happens to it."""

from pydantic import BaseModel, ConfigDict, Field

from catalyst_ai.contract.unfurl import MAX_FACT_LABEL, MAX_FACT_VALUE, MAX_FACTS, MAX_SUMMARY

MAX_RATIONALE_CHARS = 300


class ModelFact(BaseModel):
    """One labelled value as the model wrote it."""

    model_config = ConfigDict(extra="forbid")

    label: str = Field(min_length=1, max_length=MAX_FACT_LABEL)
    value: str = Field(min_length=1, max_length=MAX_FACT_VALUE)


class ModelOutput(BaseModel):
    """What a valid completion carries; anything else is `ai.output.invalid`."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(min_length=1, max_length=MAX_SUMMARY)
    facts: list[ModelFact] = Field(default_factory=list, max_length=MAX_FACTS)
    rationale: str = Field(min_length=1, max_length=MAX_RATIONALE_CHARS)


def output_schema() -> dict[str, object]:
    """Return the JSON schema handed to the provider's structured-output feature."""
    return ModelOutput.model_json_schema()
