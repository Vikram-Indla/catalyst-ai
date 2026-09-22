"""The verifier: every refusal reason, rotation across two keys, replay, and failing closed."""

from uuid import UUID

import pytest

from catalyst_ai.platform.auth import Binding, Bounds, Envelope, KeyRegistry, Refusal, Verifier
from catalyst_ai.platform.storage import MemoryStorage, StorageUnavailableError
from tests.unit.capabilities.improve_story.conftest import FrozenClock
from tools import origin

ORG = origin.ORG
OTHER = UUID("22222222-2222-7222-8222-222222222222")
CAP = "unfurl"
BODY = b'{"organization_id": "11111111-1111-7111-8111-111111111111"}'
BOUNDS = Bounds(clock_skew_s=5, max_ttl_s=60)
NOW = int(FrozenClock().now().timestamp())


def _signer(clock: FrozenClock | None = None) -> origin.Signer:
    return origin.Signer(clock=clock or FrozenClock())


def _verifier(keys: str = origin.PUBLIC_KEYS) -> Verifier:
    return Verifier(KeyRegistry.from_config(keys), MemoryStorage(FrozenClock()), BOUNDS)


def _binding(body: bytes = BODY, organization_id: UUID = ORG, capability: str = CAP) -> Binding:
    return Binding(body, organization_id, capability)


async def test_a_bound_fresh_envelope_is_verified_with_its_claims() -> None:
    header = _signer().sign(ORG, CAP, BODY, sub="member-9")
    verdict = await _verifier().verify(header, _binding(), NOW)
    assert isinstance(verdict, Envelope)
    assert verdict.organization_id == ORG
    assert verdict.capability == CAP
    assert verdict.subject == "member-9"
    assert verdict.key_id == origin.KEY_ID
    assert verdict.job_expires_at is None


@pytest.mark.parametrize(
    ("header", "reason"),
    [
        (None, Refusal.MISSING),
        ("Bearer old-token", Refusal.MALFORMED),
        ("Catalyst-Envelope onlyone", Refusal.MALFORMED),
        ("Catalyst-Envelope e30.c2ln", Refusal.MALFORMED),
    ],
    ids=["missing", "bearer", "one segment", "short signature"],
)
async def test_missing_or_malformed_headers_are_refused(
    header: str | None, reason: Refusal
) -> None:
    assert await _verifier().verify(header, _binding(), NOW) is reason


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"kid": "nobody"}, Refusal.UNKNOWN_KEY),
        ({"iss": "web"}, Refusal.WRONG_ISSUER),
        ({"aud": "someone-else"}, Refusal.WRONG_AUDIENCE),
        ({"exp": NOW + 61}, Refusal.TOO_LONG_LIVED),
        ({"iat": NOW + 6, "exp": NOW + 36}, Refusal.NOT_YET_VALID),
        ({"iat": NOW - 60, "exp": NOW - 5}, Refusal.EXPIRED),
        ({"bh": "0" * 64}, Refusal.BODY_MISMATCH),
        ({"org": str(OTHER)}, Refusal.ORGANIZATION_MISMATCH),
        ({"cap": "summarize"}, Refusal.CAPABILITY_MISMATCH),
    ],
    ids=[
        "unknown key",
        "wrong issuer",
        "wrong audience",
        "too long lived",
        "not yet valid",
        "expired",
        "body hash",
        "organisation",
        "capability",
    ],
)
async def test_each_claim_is_checked(overrides: dict[str, object], reason: Refusal) -> None:
    header = _signer().sign(ORG, CAP, BODY, **overrides)
    assert await _verifier().verify(header, _binding(), NOW) is reason


async def test_clock_skew_is_tolerated_but_no_more() -> None:
    header = _signer().sign(ORG, CAP, BODY, iat=NOW + 5, exp=NOW + 35)
    assert isinstance(await _verifier().verify(header, _binding(), NOW), Envelope)
    late = _signer().sign(ORG, CAP, BODY, iat=NOW - 34, exp=NOW - 4)
    assert isinstance(await _verifier().verify(late, _binding(), NOW), Envelope)


async def test_a_payload_edited_after_signing_is_refused() -> None:
    header = _signer().sign(ORG, CAP, BODY)
    edited = BODY.replace(b"1111", b"1112", 1)
    assert await _verifier().verify(header, _binding(edited), NOW) is Refusal.BODY_MISMATCH


async def test_an_envelope_swapped_onto_another_organisation_is_refused() -> None:
    header = _signer().sign(ORG, CAP, BODY)
    other_body = BODY.replace(b"11111111-1111-7111-8111-111111111111", str(OTHER).encode())
    verdict = await _verifier().verify(header, _binding(other_body, OTHER), NOW)
    assert verdict is Refusal.BODY_MISMATCH
    resigned = _signer().sign(ORG, CAP, other_body)
    verdict = await _verifier().verify(resigned, _binding(other_body, OTHER), NOW)
    assert verdict is Refusal.ORGANIZATION_MISMATCH


async def test_a_signature_by_an_unconfigured_key_under_a_known_id_is_refused() -> None:
    forged = origin.Signer(origin.SECOND_SEED, origin.KEY_ID, FrozenClock())
    header = forged.sign(ORG, CAP, BODY)
    assert await _verifier().verify(header, _binding(), NOW) is Refusal.BAD_SIGNATURE


async def test_a_nonce_is_honoured_once_within_its_window() -> None:
    verifier = _verifier()
    header = _signer().sign(ORG, CAP, BODY)
    assert isinstance(await verifier.verify(header, _binding(), NOW), Envelope)
    assert await verifier.verify(header, _binding(), NOW) is Refusal.REPLAYED
    assert await verifier.verify(header, _binding(), NOW + 30) is Refusal.REPLAYED
    assert await verifier.verify(header, _binding(), NOW + 36) is Refusal.EXPIRED


async def test_rotation_two_keys_verify_and_a_retired_one_refuses() -> None:
    both = _verifier(origin.BOTH_PUBLIC_KEYS)
    second = origin.Signer(origin.SECOND_SEED, origin.SECOND_KEY_ID, FrozenClock())
    assert isinstance(await both.verify(_signer().sign(ORG, CAP, BODY), _binding(), NOW), Envelope)
    assert isinstance(await both.verify(second.sign(ORG, CAP, BODY), _binding(), NOW), Envelope)
    retired_first = _verifier(second.public_entry)
    verdict = await retired_first.verify(_signer().sign(ORG, CAP, BODY), _binding(), NOW)
    assert verdict is Refusal.UNKNOWN_KEY


class _DownStorage(MemoryStorage):
    async def remember_nonce(self, nonce: str, expires_at: int, now: int) -> bool:
        raise StorageUnavailableError("ConnectionRefusedError")


async def test_a_replay_store_outage_proves_nothing() -> None:
    down = _DownStorage(FrozenClock())
    verifier = Verifier(KeyRegistry.from_config(origin.PUBLIC_KEYS), down, BOUNDS)
    header = _signer().sign(ORG, CAP, BODY)
    assert await verifier.verify(header, _binding(), NOW) is Refusal.UNVERIFIABLE
