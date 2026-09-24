"""The shape the model's text must validate against before anything else happens to it."""

from pydantic import BaseModel, ConfigDict, Field

MAX_SENTENCE_CHARS = 600
MAX_ITEMS = 10
MAX_RATIONALE_CHARS = 500


class ModelSentence(BaseModel):
    """One sentence the model wrote, with the chain ids it rests on."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(max_length=MAX_SENTENCE_CHARS)
    cites: list[str] = Field(default_factory=list, max_length=MAX_ITEMS)


class ModelOutput(BaseModel):
    """What a valid completion carries; anything else is `ai.output.invalid`."""

    model_config = ConfigDict(extra="forbid")

    summary: list[ModelSentence] = Field(default_factory=list, max_length=MAX_ITEMS)
    highlights: list[ModelSentence] = Field(default_factory=list, max_length=MAX_ITEMS)
    risks: list[ModelSentence] = Field(default_factory=list, max_length=MAX_ITEMS)
    asks: list[ModelSentence] = Field(default_factory=list, max_length=MAX_ITEMS)
    unsupported: list[str] = Field(default_factory=list, max_length=MAX_ITEMS)
    empty_reason: str | None = None
    rationale: str = Field(min_length=1, max_length=MAX_RATIONALE_CHARS)


def sentences_of(output: ModelOutput) -> list[tuple[str, ModelSentence]]:
    """Return every (field, sentence) pair of the completion."""
    fields = (
        ("summary", output.summary),
        ("highlights", output.highlights),
        ("risks", output.risks),
        ("asks", output.asks),
    )
    return [(name, sentence) for name, sentences in fields for sentence in sentences]


def prose_of(output: ModelOutput) -> str:
    """Return every sentence and note of the completion as one text."""
    texts = [sentence.text for _, sentence in sentences_of(output)] + list(output.unsupported)
    return "\n".join(texts)


def output_schema() -> dict[str, object]:
    """Return the JSON schema handed to the provider's structured-output feature."""
    return ModelOutput.model_json_schema()
