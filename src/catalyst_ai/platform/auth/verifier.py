"""Verify an envelope against a request: signature, audience, time, nonce, body, tenant, capability.

Every refusal is one reason from a closed list — for the security log and the counter, never
for the caller, who sees `auth.origin.invalid` and nothing else.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from catalyst_ai.platform.auth.envelope import (
    AUDIENCE,
    ISSUER,
    Decoded,
    Envelope,
    MalformedEnvelopeError,
    body_hash,
    decode,
)
from catalyst_ai.platform.auth.keys import KeyRegistry
from catalyst_ai.platform.storage import Storage, StorageUnavailableError


class Refusal(StrEnum):
    """Why a proof of origin was not accepted."""

    MISSING = "missing"
    MALFORMED = "malformed"
    UNKNOWN_KEY = "unknown_key"
    BAD_SIGNATURE = "bad_signature"
    WRONG_ISSUER = "wrong_issuer"
    WRONG_AUDIENCE = "wrong_audience"
    TOO_LONG_LIVED = "too_long_lived"
    NOT_YET_VALID = "not_yet_valid"
    EXPIRED = "expired"
    REPLAYED = "replayed"
    BODY_MISMATCH = "body_mismatch"
    ORGANIZATION_MISMATCH = "organization_mismatch"
    CAPABILITY_MISMATCH = "capability_mismatch"
    UNVERIFIABLE = "unverifiable"


@dataclass(frozen=True)
class Binding:
    """What the request itself says, for the envelope to be bound to."""

    body: bytes
    organization_id: UUID | None
    capability: str | None


@dataclass(frozen=True)
class Bounds:
    """The tolerances: how far a clock may drift and how long a proof may live."""

    clock_skew_s: int
    max_ttl_s: int


def _static_refusal(envelope: Envelope, bounds: Bounds, now: int) -> Refusal | None:
    checks = (
        (envelope.issuer != ISSUER, Refusal.WRONG_ISSUER),
        (envelope.audience != AUDIENCE, Refusal.WRONG_AUDIENCE),
        (envelope.expires_at - envelope.issued_at > bounds.max_ttl_s, Refusal.TOO_LONG_LIVED),
        (now + bounds.clock_skew_s < envelope.issued_at, Refusal.NOT_YET_VALID),
        (now - bounds.clock_skew_s >= envelope.expires_at, Refusal.EXPIRED),
    )
    return next((reason for failed, reason in checks if failed), None)


def _binding_refusal(envelope: Envelope, binding: Binding) -> Refusal | None:
    checks = (
        (envelope.body_hash != body_hash(binding.body), Refusal.BODY_MISMATCH),
        (envelope.organization_id != binding.organization_id, Refusal.ORGANIZATION_MISMATCH),
        (envelope.capability != binding.capability, Refusal.CAPABILITY_MISMATCH),
    )
    return next((reason for failed, reason in checks if failed), None)


def check_signature(decoded: Decoded, keys: KeyRegistry) -> Refusal | None:
    """Return why the signature is not the backend's, or None when it is."""
    if decoded.envelope.key_id not in keys.key_ids:
        return Refusal.UNKNOWN_KEY
    if not keys.verify(decoded.envelope.key_id, decoded.signed, decoded.signature):
        return Refusal.BAD_SIGNATURE
    return None


class Verifier:
    """The one place a request is proven to come from the backend, or refused."""

    def __init__(self, keys: KeyRegistry, replay: Storage, bounds: Bounds) -> None:
        """Hold the keys, the storage that remembers nonces, and the tolerances."""
        self._keys = keys
        self._replay = replay
        self._bounds = bounds

    async def verify(self, header: str | None, binding: Binding, now: int) -> Envelope | Refusal:
        """Return the verified envelope, or the reason it was refused."""
        try:
            decoded = decode(header)
        except MalformedEnvelopeError:
            return Refusal.MISSING if header is None else Refusal.MALFORMED
        envelope = decoded.envelope
        refusal = check_signature(decoded, self._keys)
        refusal = refusal or _static_refusal(envelope, self._bounds, now)
        refusal = refusal or _binding_refusal(envelope, binding)
        if refusal is None:
            refusal = await self._once(envelope, now)
        return envelope if refusal is None else refusal

    async def _once(self, envelope: Envelope, now: int) -> Refusal | None:
        """Honour the nonce once; when the store cannot answer, nothing is proven (fail closed)."""
        until = envelope.expires_at + self._bounds.clock_skew_s
        try:
            fresh = await self._replay.remember_nonce(envelope.nonce, until, now)
        except StorageUnavailableError:
            return Refusal.UNVERIFIABLE
        return None if fresh else Refusal.REPLAYED
