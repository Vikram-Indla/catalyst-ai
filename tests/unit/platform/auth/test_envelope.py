"""The wire form: what decodes, what is malformed and why."""

import base64
import json

import pytest

from catalyst_ai.platform.auth import compact, decode
from catalyst_ai.platform.auth.envelope import Malformed, MalformedEnvelopeError, encode_claims
from tools import origin

SIGNATURE = base64.urlsafe_b64encode(bytes(64)).rstrip(b"=").decode()


def _header(claims: dict[str, object]) -> str:
    return compact(encode_claims(claims), bytes(64))


def _claims(**overrides: object) -> dict[str, object]:
    return origin.SIGNER.claims(origin.ORG, "unfurl", b"{}", **overrides)


def test_decode_returns_the_claims_the_signed_bytes_and_the_signature() -> None:
    header = origin.SIGNER.sign(origin.ORG, "unfurl", b"{}", job_exp=99)
    decoded = decode(header)
    assert decoded.envelope.capability == "unfurl"
    assert decoded.envelope.job_expires_at == 99
    assert len(decoded.signature) == 64
    segment = header.removeprefix("Catalyst-Envelope ").split(".")[0]
    assert decoded.signed == segment.encode()
    padded = segment + "=" * (-len(segment) % 4)
    assert json.loads(base64.urlsafe_b64decode(padded))["cap"] == "unfurl"


@pytest.mark.parametrize(
    ("header", "reason"),
    [
        (None, Malformed.NO_ENVELOPE),
        ("Bearer x", Malformed.NO_ENVELOPE),
        ("Catalyst-Envelope nodot", Malformed.NOT_TWO_SEGMENTS),
        ("Catalyst-Envelope .sig", Malformed.NOT_TWO_SEGMENTS),
        ("Catalyst-Envelope e30.c", Malformed.NOT_BASE64URL),
        ("Catalyst-Envelope e30.c2ln", Malformed.SIGNATURE_LENGTH),
        (f"Catalyst-Envelope e.{SIGNATURE}", Malformed.NOT_BASE64URL),
        (f"Catalyst-Envelope bm90anNvbg.{SIGNATURE}", Malformed.CLAIMS_NOT_JSON),
        (f"Catalyst-Envelope WzFd.{SIGNATURE}", Malformed.CLAIMS_NOT_OBJECT),
        (f"Catalyst-Envelope e30.{SIGNATURE}", Malformed.CLAIM_MISSING),
        (_header(_claims(org="not-a-uuid")), Malformed.ORG_NOT_UUID),
        (_header(_claims(cap="")), Malformed.CLAIM_NOT_TEXT),
        (_header(_claims(sub="x" * 257)), Malformed.CLAIM_NOT_TEXT),
        (_header(_claims(iat="soon")), Malformed.CLAIM_NOT_TIME),
        (_header(_claims(exp=True)), Malformed.CLAIM_NOT_TIME),
        (_header(_claims(job_exp=-1)), Malformed.CLAIM_NOT_TIME),
        (_header(_claims(pad="x" * 5000)), Malformed.CLAIMS_TOO_LARGE),
    ],
    ids=[
        "none",
        "bearer",
        "no dot",
        "empty claims",
        "signature not base64url",
        "signature short",
        "claims not base64url",
        "claims not json",
        "claims a list",
        "claims empty",
        "org not uuid",
        "empty text claim",
        "text claim too long",
        "iat text",
        "exp bool",
        "job_exp negative",
        "claims too large",
    ],
)
def test_malformed_headers_carry_their_reason(header: str | None, reason: Malformed) -> None:
    with pytest.raises(MalformedEnvelopeError) as raised:
        decode(header)
    assert raised.value.reason is reason
