"""The provider-call row: organisation, capability, versions, model, tokens, cost, outcome."""

import logging
from uuid import UUID

from pydantic import BaseModel, ConfigDict

log = logging.getLogger("catalyst_ai.provider_calls")


class ProviderCallRow(BaseModel):
    """Every field a call may log; there is no field for content and none will be added."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    organization_id: UUID
    capability: str
    capability_version: str
    prompt_version: str
    model_alias: str
    model_id: str
    input_tokens: int
    output_tokens: int
    cost_micros: int
    latency_ms: int
    cache_hit: bool
    outcome: str
    request_id: str


def log_provider_call(row: ProviderCallRow) -> None:
    """Emit the row as one structured line; storage of the row arrives with the storage package."""
    log.info("provider call", extra=row.model_dump(mode="json"))
