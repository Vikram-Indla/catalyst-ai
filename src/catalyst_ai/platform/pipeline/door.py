"""Stage 2 for every capability: the switch, the contract version, the scanner, the tenant cap."""

from dataclasses import dataclass
from uuid import UUID

from catalyst_ai.config import CapabilitySettings
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.cache import cache_key, idempotency_key
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.platform.safety import refuse_if_needed
from catalyst_ai.providers.port import ModelAlias

ESTIMATE_OUTPUT_TOKENS = 800


@dataclass(frozen=True)
class Door:
    """What the door needs to know about the capability and the request."""

    name: str
    version: str
    prompt_version: str
    alias: str
    settings: CapabilitySettings
    organization_id: UUID
    capability_version: str
    user_texts: dict[str, str | None]
    canonical_input: dict[str, object]
    idempotency: str | None


def admit(door: Door, runtime: RuntimeContext) -> str:
    """Refuse or admit; return the cache key the run resolves through."""
    if not door.settings.enabled:
        raise Error(ErrorCode.CAPABILITY_DISABLED, f"{door.name} is disabled")
    if door.capability_version.split(".")[0] != door.version.split(".")[0]:
        raise Error(
            ErrorCode.CONTRACT_VERSION_MISMATCH, f"this service serves {door.name} {door.version}"
        )
    refuse_if_needed(door.user_texts)
    joined = "\n".join(text for text in door.user_texts.values() if text)
    estimate = (
        runtime.provider.count_tokens(ModelAlias(door.alias), joined) + ESTIMATE_OUTPUT_TOKENS
    )
    runtime.budgets.reserve(door.organization_id, estimate)
    if door.idempotency:
        return idempotency_key(door.organization_id, door.name, door.idempotency)
    versions = (door.version, door.prompt_version, door.alias)
    return cache_key(door.organization_id, door.name, versions, door.canonical_input)
