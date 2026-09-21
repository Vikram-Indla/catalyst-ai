"""The shape the model's text must validate against before anything else happens to it."""

from pydantic import BaseModel, ConfigDict, Field

MAX_SUMMARY_CHARS = 12_000
MAX_RATIONALE_CHARS = 500
MAX_MENTIONED = 50
MAX_ENTRIES = 50
MAX_LINES = 20


class ModelStandup(BaseModel):
    """One participant's done, doing and blocked lines as the model wrote them."""

    model_config = ConfigDict(extra="forbid")

    participant: str
    done: list[str] = Field(max_length=MAX_LINES)
    doing: list[str] = Field(max_length=MAX_LINES)
    blocked: list[str] = Field(max_length=MAX_LINES)


class ModelDigest(BaseModel):
    """One kind's change lines as the model wrote them; it states no count."""

    model_config = ConfigDict(extra="forbid")

    kind: str
    changes: list[str] = Field(max_length=MAX_LINES)


class ModelOutput(BaseModel):
    """What a valid completion carries; anything else is `ai.output.invalid`."""

    model_config = ConfigDict(extra="forbid")

    summary: str = Field(max_length=MAX_SUMMARY_CHARS)
    participants_mentioned: list[str] = Field(max_length=MAX_MENTIONED)
    empty_reason: str | None = None
    rationale: str = Field(min_length=1, max_length=MAX_RATIONALE_CHARS)
    standup: list[ModelStandup] = Field(default_factory=list, max_length=MAX_ENTRIES)
    digest: list[ModelDigest] = Field(default_factory=list, max_length=MAX_ENTRIES)


def prose_of(output: ModelOutput) -> str:
    """Return every free-text field of a completion, joined for the leakage scan."""
    standup = [line for e in output.standup for line in [*e.done, *e.doing, *e.blocked]]
    digest = [line for g in output.digest for line in g.changes]
    return "\n".join([output.summary, *standup, *digest])


def output_schema() -> dict[str, object]:
    """Return the JSON schema handed to the provider's structured-output feature."""
    return ModelOutput.model_json_schema()
