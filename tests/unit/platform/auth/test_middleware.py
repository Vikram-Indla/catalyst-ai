"""verify_token: constant-time, every configured token, malformed headers refused."""

import pytest
from pydantic import SecretStr

from catalyst_ai.platform.auth import verify_token

TOKENS = [SecretStr("one"), SecretStr("two")]


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("Bearer one", True),
        ("Bearer two", True),
        ("Bearer three", False),
        ("bearer one", False),
        ("one", False),
        ("", False),
        (None, False),
    ],
    ids=["first", "second", "unknown", "lowercase scheme", "no scheme", "empty", "missing"],
)
def test_verify_token(header: str | None, expected: bool) -> None:
    assert verify_token(header, TOKENS) is expected
