"""Proof of origin for every operation: the envelope, the keys, the verifier, the job gate."""

from catalyst_ai.platform.auth.envelope import (
    Envelope,
    MalformedEnvelopeError,
    body_hash,
    compact,
    decode,
    encode_claims,
)
from catalyst_ai.platform.auth.jobs import JobState, Quarantine, StoredProof, verify_stored
from catalyst_ai.platform.auth.keys import KeyRegistry, PublicKeyConfigError
from catalyst_ai.platform.auth.middleware import (
    EXEMPT_PATHS,
    Lookup,
    OriginMiddleware,
    capability_of,
    envelope_of,
    organization_of,
)
from catalyst_ai.platform.auth.verifier import Binding, Bounds, Refusal, Verifier

__all__ = [
    "EXEMPT_PATHS",
    "Binding",
    "Bounds",
    "Envelope",
    "JobState",
    "KeyRegistry",
    "Lookup",
    "MalformedEnvelopeError",
    "OriginMiddleware",
    "PublicKeyConfigError",
    "Quarantine",
    "Refusal",
    "StoredProof",
    "Verifier",
    "body_hash",
    "capability_of",
    "compact",
    "decode",
    "encode_claims",
    "envelope_of",
    "organization_of",
    "verify_stored",
]
