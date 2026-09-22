"""The proof of origin: a compact, signed, bound set of claims the backend puts on every call.

Wire form, in `Authorization: Catalyst-Envelope <claims>.<signature>`: `claims` is the
base64url (unpadded) of a JSON object; `signature` is the base64url of the 64-byte Ed25519
signature over the ASCII bytes of the `claims` segment exactly as sent. The service decodes,
verifies the signature with the public key the `kid` names, and binds the claims to the request.
"""

import base64
import binascii
import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

SCHEME = "Catalyst-Envelope "
ISSUER = "backend"
AUDIENCE = "catalyst-ai"
SIGNATURE_BYTES = 64
MAX_CLAIMS_BYTES = 4096
REQUIRED = ("iss", "aud", "org", "cap", "sub", "iat", "exp", "jti", "kid", "bh")
MAX_TEXT = 256


@dataclass(frozen=True)
class Envelope:
    """The claims of one proof: who issued it, for whom, bound to what, valid when."""

    issuer: str
    audience: str
    organization_id: UUID
    capability: str
    subject: str
    issued_at: int
    expires_at: int
    nonce: str
    key_id: str
    body_hash: str
    job_expires_at: int | None


@dataclass(frozen=True)
class Decoded:
    """An envelope with the bytes its signature covers and the signature itself."""

    envelope: Envelope
    signed: bytes
    signature: bytes


class Malformed(StrEnum):
    """How a header failed to be an envelope; for the security log, never the caller."""

    NO_ENVELOPE = "no_envelope"
    NOT_TWO_SEGMENTS = "not_two_segments"
    NOT_BASE64URL = "not_base64url"
    SIGNATURE_LENGTH = "signature_length"
    CLAIMS_TOO_LARGE = "claims_too_large"
    CLAIMS_NOT_JSON = "claims_not_json"
    CLAIMS_NOT_OBJECT = "claims_not_object"
    CLAIM_MISSING = "claim_missing"
    CLAIM_NOT_TEXT = "claim_not_text"
    CLAIM_NOT_TIME = "claim_not_time"
    ORG_NOT_UUID = "org_not_uuid"


class MalformedEnvelopeError(ValueError):
    """The header is not an envelope."""

    def __init__(self, reason: Malformed) -> None:
        """Carry the reason."""
        super().__init__(reason.value)
        self.reason = reason


def body_hash(body: bytes) -> str:
    """Return the hash the `bh` claim must carry: hex SHA-256 over the request body bytes."""
    return hashlib.sha256(body).hexdigest()


def _b64decode(segment: str) -> bytes:
    padded = segment + "=" * (-len(segment) % 4)
    try:
        return base64.urlsafe_b64decode(padded.encode("ascii"))
    except (binascii.Error, UnicodeEncodeError) as error:
        raise MalformedEnvelopeError(Malformed.NOT_BASE64URL) from error


def _text(claims: dict[str, object], name: str) -> str:
    value = claims.get(name)
    if not isinstance(value, str) or not value or len(value) > MAX_TEXT:
        raise MalformedEnvelopeError(Malformed.CLAIM_NOT_TEXT)
    return value


def _moment(claims: dict[str, object], name: str) -> int:
    value = claims.get(name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise MalformedEnvelopeError(Malformed.CLAIM_NOT_TIME)
    return value


def _claims_of(segment: str) -> dict[str, object]:
    raw = _b64decode(segment)
    if len(raw) > MAX_CLAIMS_BYTES:
        raise MalformedEnvelopeError(Malformed.CLAIMS_TOO_LARGE)
    try:
        claims = json.loads(raw)
    except ValueError as error:
        raise MalformedEnvelopeError(Malformed.CLAIMS_NOT_JSON) from error
    if not isinstance(claims, dict):
        raise MalformedEnvelopeError(Malformed.CLAIMS_NOT_OBJECT)
    if any(name not in claims for name in REQUIRED):
        raise MalformedEnvelopeError(Malformed.CLAIM_MISSING)
    return claims


def _envelope_of(claims: dict[str, object]) -> Envelope:
    try:
        organization_id = UUID(_text(claims, "org"))
    except ValueError as error:
        raise MalformedEnvelopeError(Malformed.ORG_NOT_UUID) from error
    job_expires_at = _moment(claims, "job_exp") if "job_exp" in claims else None
    return Envelope(
        issuer=_text(claims, "iss"),
        audience=_text(claims, "aud"),
        organization_id=organization_id,
        capability=_text(claims, "cap"),
        subject=_text(claims, "sub"),
        issued_at=_moment(claims, "iat"),
        expires_at=_moment(claims, "exp"),
        nonce=_text(claims, "jti"),
        key_id=_text(claims, "kid"),
        body_hash=_text(claims, "bh"),
        job_expires_at=job_expires_at,
    )


def decode(header: str | None) -> Decoded:
    """Parse the header into claims, the signed bytes and the signature; verify nothing."""
    if header is None or not header.startswith(SCHEME):
        raise MalformedEnvelopeError(Malformed.NO_ENVELOPE)
    compact = header.removeprefix(SCHEME).strip()
    claims_segment, dot, signature_segment = compact.partition(".")
    if not dot or not claims_segment or not signature_segment:
        raise MalformedEnvelopeError(Malformed.NOT_TWO_SEGMENTS)
    signature = _b64decode(signature_segment)
    if len(signature) != SIGNATURE_BYTES:
        raise MalformedEnvelopeError(Malformed.SIGNATURE_LENGTH)
    envelope = _envelope_of(_claims_of(claims_segment))
    return Decoded(envelope=envelope, signed=claims_segment.encode("ascii"), signature=signature)


def compact(claims_segment: bytes, signature: bytes) -> str:
    """Return the header value for signed claims; the one encoder, used by the tests' signer."""
    encoded = base64.urlsafe_b64encode(signature).rstrip(b"=").decode("ascii")
    return SCHEME + claims_segment.decode("ascii") + "." + encoded


def encode_claims(claims: dict[str, object]) -> bytes:
    """Return the claims segment bytes for a claims object; what a signer signs."""
    raw = json.dumps(claims, separators=(",", ":"), sort_keys=True).encode()
    return base64.urlsafe_b64encode(raw).rstrip(b"=")
