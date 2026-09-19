"""The cache key: tenant, capability, versions, alias and the canonical classified input."""

import hashlib
import json
from uuid import UUID

SEPARATOR = "\x1f"


def cache_key(
    organization_id: UUID,
    capability: str,
    versions: tuple[str, str, str],
    canonical_input: dict[str, object],
) -> str:
    """Hash every component that decides a result; any component changing invalidates."""
    capability_version, prompt_version, alias = versions
    payload = json.dumps(canonical_input, sort_keys=True, separators=(",", ":"), default=str)
    parts = (str(organization_id), capability, capability_version, prompt_version, alias, payload)
    return hashlib.sha256(SEPARATOR.join(parts).encode()).hexdigest()


def idempotency_key(organization_id: UUID, capability: str, header: str) -> str:
    """Return the key an `Idempotency-Key` header resolves through, scoped by organisation."""
    return hashlib.sha256(
        SEPARATOR.join((str(organization_id), capability, header)).encode()
    ).hexdigest()
