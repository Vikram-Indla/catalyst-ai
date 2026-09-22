"""A job row is never trusted for being in the table: the attacker's row is quarantined, never run."""

from uuid import UUID

import pytest

from catalyst_ai.platform.auth import (
    Envelope,
    KeyRegistry,
    Quarantine,
    Refusal,
    StoredProof,
    body_hash,
    verify_stored,
)
from tests.unit.capabilities.improve_story.conftest import FrozenClock
from tools import origin

ORG = origin.ORG
OTHER = UUID("22222222-2222-7222-8222-222222222222")
CAP = "documents"
PAYLOAD = b'{"organization_id": "11111111-1111-7111-8111-111111111111", "pages": []}'
NOW = int(FrozenClock().now().timestamp())
KEYS = KeyRegistry.from_config(origin.PUBLIC_KEYS)
JOB_WINDOW_S = 3600


def _row(
    envelope: str,
    organization_id: UUID = ORG,
    capability: str = CAP,
    payload_hash: str | None = None,
) -> StoredProof:
    return StoredProof(envelope, organization_id, capability, payload_hash or body_hash(PAYLOAD))


def _signed(**overrides: object) -> str:
    signer = origin.Signer(clock=FrozenClock())
    return signer.sign(ORG, CAP, PAYLOAD, job_exp=NOW + JOB_WINDOW_S, **overrides)


def test_a_row_the_api_stored_runs_under_its_envelope_after_the_request_window() -> None:
    verdict = verify_stored(_row(_signed()), KEYS, NOW + 600)
    assert isinstance(verdict, Envelope)
    assert verdict.organization_id == ORG
    assert verdict.job_expires_at == NOW + JOB_WINDOW_S


@pytest.mark.parametrize(
    ("row", "reason"),
    [
        (_row(""), Refusal.MALFORMED),
        (_row("Catalyst-Envelope forged.forged"), Refusal.MALFORMED),
        (_row(_signed(), organization_id=OTHER), Refusal.ORGANIZATION_MISMATCH),
        (_row(_signed(), capability="summarize"), Refusal.CAPABILITY_MISMATCH),
        (_row(_signed(), payload_hash=body_hash(PAYLOAD + b" ")), Refusal.BODY_MISMATCH),
        (_row(_signed(kid="nobody")), Refusal.UNKNOWN_KEY),
        (_row(_signed(iss="web")), Refusal.WRONG_ISSUER),
    ],
    ids=[
        "inserted by hand, no envelope",
        "inserted by hand, a made-up envelope",
        "envelope copied onto another organisation's row",
        "envelope copied onto another capability's row",
        "payload edited after the api stored it",
        "signed by an unknown key",
        "wrong issuer",
    ],
)
def test_the_attackers_rows_are_quarantined(row: StoredProof, reason: Refusal) -> None:
    assert verify_stored(row, KEYS, NOW) is reason


def test_a_forged_signature_under_a_known_key_id_is_quarantined() -> None:
    forged = origin.Signer(origin.SECOND_SEED, origin.KEY_ID, FrozenClock())
    header = forged.sign(ORG, CAP, PAYLOAD, job_exp=NOW + JOB_WINDOW_S)
    assert verify_stored(_row(header), KEYS, NOW) is Refusal.BAD_SIGNATURE


def test_a_job_needs_its_own_window_and_stops_when_it_closes() -> None:
    no_window = origin.Signer(clock=FrozenClock()).sign(ORG, CAP, PAYLOAD)
    assert verify_stored(_row(no_window), KEYS, NOW) is Quarantine.NO_JOB_WINDOW
    assert verify_stored(_row(_signed()), KEYS, NOW + JOB_WINDOW_S) is Quarantine.JOB_EXPIRED
