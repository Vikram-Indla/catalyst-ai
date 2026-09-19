"""Shapes every request and response share."""

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

DATA_CLASS_KEY = "data_class"


def classified(data_class: str, description: str) -> dict[str, str]:
    """Return the schema extra that declares a request field's data class."""
    return {DATA_CLASS_KEY: data_class, "description": description}


class RequestEnvelope(BaseModel):
    """What every capability request carries: the tenant and the contract version."""

    model_config = ConfigDict(extra="forbid")

    organization_id: Annotated[
        UUID, Field(json_schema_extra=classified("INTERNAL", "The tenant every row is scoped by"))
    ]
    capability_version: Annotated[
        str,
        Field(
            pattern=r"^\d+\.\d+\.\d+$",
            json_schema_extra=classified("PUBLIC", "The version the caller was built against"),
        ),
    ]


class Usage(BaseModel):
    """Tokens, cost and latency of one call; cost in micro-dollars, latency in milliseconds."""

    model_config = ConfigDict(extra="forbid")

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_micros: int = Field(ge=0)
    latency_ms: int = Field(ge=0)
    cache_hit: bool


class ResponseEnvelope(BaseModel):
    """What every capability response carries: provenance of the versions that produced it."""

    model_config = ConfigDict(extra="forbid")

    capability_version: str
    prompt_version: str
    model: str
    eval_set_version: str
    usage: Usage
    request_id: str
