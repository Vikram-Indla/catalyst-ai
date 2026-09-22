"""A job is never trusted for being in the table: its stored proof is verified again before it runs.

The job model (`ADR-007`) has no table yet; when it lands, a row carries the envelope exactly as
the API verified it (the backend's signature — the service can re-sign nothing) and the hash of
the payload the envelope's `bh` covered. The worker calls `verify_stored` before executing; a
row that fails is `quarantined` with the reason and never runs. A row inserted by anything but
the API's verified path has no valid proof and therefore never runs.
"""

from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID

from catalyst_ai.platform.auth.envelope import (
    AUDIENCE,
    ISSUER,
    Envelope,
    MalformedEnvelopeError,
    decode,
)
from catalyst_ai.platform.auth.keys import KeyRegistry
from catalyst_ai.platform.auth.verifier import Refusal, check_signature


class JobState(StrEnum):
    """Where a job row is; `quarantined` is terminal and never executed."""

    QUEUED = "queued"
    VERIFIED = "verified"
    RUNNING = "running"
    DONE = "done"
    QUARANTINED = "quarantined"


class Quarantine(StrEnum):
    """Why a stored proof did not clear the worker's gate; the reasons beyond the request's."""

    NO_JOB_WINDOW = "no_job_window"
    JOB_EXPIRED = "job_expired"


@dataclass(frozen=True)
class StoredProof:
    """What a job row holds beside its payload: the proof and the bindings to check it against."""

    envelope: str
    organization_id: UUID
    capability: str
    payload_hash: str


def _bound(envelope: Envelope, stored: StoredProof) -> Refusal | None:
    checks = (
        (envelope.issuer != ISSUER, Refusal.WRONG_ISSUER),
        (envelope.audience != AUDIENCE, Refusal.WRONG_AUDIENCE),
        (envelope.organization_id != stored.organization_id, Refusal.ORGANIZATION_MISMATCH),
        (envelope.capability != stored.capability, Refusal.CAPABILITY_MISMATCH),
        (envelope.body_hash != stored.payload_hash, Refusal.BODY_MISMATCH),
    )
    return next((reason for failed, reason in checks if failed), None)


def _within_window(envelope: Envelope, now: int) -> Envelope | Quarantine:
    if envelope.job_expires_at is None:
        return Quarantine.NO_JOB_WINDOW
    return Quarantine.JOB_EXPIRED if now >= envelope.job_expires_at else envelope


def verify_stored(
    stored: StoredProof, keys: KeyRegistry, now: int
) -> Envelope | Refusal | Quarantine:
    """Return the envelope a job may run under, or why it is quarantined instead.

    The request window (`exp`) does not apply — the job was accepted inside it; the job window
    (`job_exp`, the capability's budget window the backend signed) does.
    """
    try:
        decoded = decode(stored.envelope)
    except MalformedEnvelopeError:
        return Refusal.MALFORMED
    refusal = check_signature(decoded, keys) or _bound(decoded.envelope, stored)
    return refusal if refusal is not None else _within_window(decoded.envelope, now)
