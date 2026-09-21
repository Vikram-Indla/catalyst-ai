"""The shapes the model's text must validate against: an answer of claims, a draft of sections."""

from pydantic import BaseModel, ConfigDict, Field

MAX_LINE_CHARS = 2_000
MAX_LIST = 60
MAX_RATIONALE_CHARS = 500


class ModelClaim(BaseModel):
    """One sentence of the answer with the passages it rests on."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=MAX_LINE_CHARS)
    chunk_ids: list[str] = Field(default_factory=list, max_length=MAX_LIST)


class AskOutput(BaseModel):
    """What a valid answer carries; anything else is `ai.output.invalid`."""

    model_config = ConfigDict(extra="forbid")

    claims: list[ModelClaim] = Field(default_factory=list, max_length=MAX_LIST)
    not_found: bool = False
    rationale: str = Field(min_length=1, max_length=MAX_RATIONALE_CHARS)


class ModelSection(BaseModel):
    """One section of a draft with the source ids it rests on."""

    model_config = ConfigDict(extra="forbid")

    heading: str = Field(max_length=MAX_LINE_CHARS)
    text: str = Field(max_length=MAX_LINE_CHARS * 4)
    sources: list[str] = Field(default_factory=list, max_length=MAX_LIST)


class DraftOutput(BaseModel):
    """What a valid draft carries; anything else is `ai.output.invalid`."""

    model_config = ConfigDict(extra="forbid")

    title: str = Field(default="", max_length=MAX_LINE_CHARS)
    sections: list[ModelSection] = Field(default_factory=list, max_length=MAX_LIST)
    empty_reason: str | None = None
    rationale: str = Field(min_length=1, max_length=MAX_RATIONALE_CHARS)


def ask_prose(output: AskOutput) -> str:
    """Return every free-text field of an answer, joined for the scans."""
    return "\n".join(claim.text for claim in output.claims)


def draft_prose(output: DraftOutput) -> str:
    """Return every free-text field of a draft, joined for the scans."""
    return "\n".join([output.title, *(f"{s.heading}\n{s.text}" for s in output.sections)])


def ask_schema() -> dict[str, object]:
    """Return the JSON schema handed to the provider for an answer."""
    return AskOutput.model_json_schema()


def draft_schema() -> dict[str, object]:
    """Return the JSON schema handed to the provider for a draft."""
    return DraftOutput.model_json_schema()
