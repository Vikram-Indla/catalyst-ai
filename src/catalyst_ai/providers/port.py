"""The Provider port: the only way a model is reached, and the models that cross it."""

from collections.abc import AsyncIterator
from enum import StrEnum
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from catalyst_ai.contract.envelopes import Usage

MAX_OUTPUT_TOKENS_CEILING = 65_536


class ModelAlias(StrEnum):
    """What a capability names; the register resolves it to a provider and a model id."""

    TEXT_DEFAULT = "text-default"
    TEXT_FAST = "text-fast"
    TEXT_LONG = "text-long"
    EMBED_DEFAULT = "embed-default"
    GRADER_DEFAULT = "grader-default"


class Segment(BaseModel):
    """One part of the request to the model; user segments are data, never instructions."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal["system", "developer", "user"]
    name: str = Field(min_length=1)
    text: str


class GenerateRequest(BaseModel):
    """A generation call: segments, the output schema, bounds and the tenant for the log."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    organization_id: UUID
    request_id: str = Field(min_length=1)
    capability: str = Field(min_length=1)
    alias: ModelAlias
    segments: list[Segment] = Field(min_length=1)
    output_schema: dict[str, object] | None = None
    temperature: float = Field(ge=0.0, le=2.0)
    max_output_tokens: int = Field(gt=0, le=MAX_OUTPUT_TOKENS_CEILING)
    timeout_ms: int = Field(gt=0)


class GenerateResult(BaseModel):
    """What the model returned, with the concrete model id and the usage the adapter counted."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    text: str
    model_id: str
    usage: Usage


class StreamFrame(BaseModel):
    """One frame of a streamed generation; exactly one terminal frame ends a stream."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    kind: Literal["delta", "usage", "done", "error"]
    text: str = ""
    usage: Usage | None = None
    model_id: str | None = None
    error_code: str | None = None


class EmbedRequest(BaseModel):
    """An embedding call over one or more texts."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    organization_id: UUID
    capability: str = Field(min_length=1)
    alias: ModelAlias
    texts: list[str] = Field(min_length=1)
    purpose: Literal["document", "query"] = "document"
    timeout_ms: int = Field(gt=0)


class EmbedResult(BaseModel):
    """One vector per input text, with the model that produced them."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    vectors: list[list[float]]
    model_id: str
    usage: Usage


class Provider(Protocol):
    """Reach a model; adapters implement it, capabilities call it in the pipeline's call stage."""

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        """Run one generation."""
        ...

    def stream(self, request: GenerateRequest) -> AsyncIterator[StreamFrame]:
        """Run one generation as frames ending in a terminal frame."""
        ...

    async def embed(self, request: EmbedRequest) -> EmbedResult:
        """Embed the texts."""
        ...

    def count_tokens(self, alias: ModelAlias, text: str) -> int:
        """Count the tokens the alias's model would see for the text."""
        ...

    def model_id(self, alias: ModelAlias) -> str:
        """Return the concrete model the alias resolves to right now."""
        ...
