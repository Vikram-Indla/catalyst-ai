"""The door: every RESTRICTED pattern and control sequence is refused with a class, never a value."""

import pytest

from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.safety import refuse_if_needed, scan_fields
from catalyst_ai.platform.safety.input import MAX_TOTAL_CHARS, ReasonClass


@pytest.mark.parametrize(
    ("value", "label"),
    [
        ("mail me at someone@example.com", "email"),
        ("-----BEGIN RSA PRIVATE KEY-----", "private_key"),
        ("key AKIAABCDEFGHIJKLMNOP here", "aws_access_key"),
        ("sk-abcdefghijklmnopqrstuvwxyz", "bearer_like_key"),
        ("AIzaSyA-abcdefghijklmnopqrstuvwxyz01234", "google_api_key"),
        ("eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.abcdefghijklmnop", "jwt"),
        ("host 10.0.0.12 is down", "ipv4"),
    ],
    ids=["email", "private key", "aws key", "sk key", "google key", "jwt", "ipv4"],
)
def test_restricted_patterns_refused(value: str, label: str) -> None:
    details = scan_fields({"description": value})
    assert [d.code for d in details] == [ReasonClass.RESTRICTED_PATTERN.value]
    assert label in details[0].message
    assert value not in details[0].message


def test_control_sequence_refused() -> None:
    details = scan_fields({"title": "a\x00b"})
    assert details[0].code == ReasonClass.CONTROL_SEQUENCE.value


def test_too_large_refused_as_its_own_code() -> None:
    with pytest.raises(Error) as caught:
        refuse_if_needed({"description": "x" * (MAX_TOTAL_CHARS + 1)})
    assert caught.value.code is ErrorCode.INPUT_TOO_LARGE


def test_rejected_wins_over_too_large() -> None:
    with pytest.raises(Error) as caught:
        refuse_if_needed({"a": "x" * (MAX_TOTAL_CHARS + 1), "b": "user@example.com"})
    assert caught.value.code is ErrorCode.INPUT_REJECTED


def test_clean_fields_pass() -> None:
    refuse_if_needed({"title": "Export board", "description": None, "hint": ""})
