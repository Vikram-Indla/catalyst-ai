"""The completion's shape: prose, the marker, the tail; what may be shown while it grows."""

import pytest

from catalyst_ai.capabilities.assistant.schema import MARKER, split, visible
from tests.unit.capabilities.assistant.conftest import completion


def test_split_returns_the_prose_and_the_tail() -> None:
    prose, tail = split(completion("Hello there. [1]", not_found=False, rationale="because"))
    assert prose == "Hello there. [1]"
    assert tail.not_found is False
    assert tail.rationale == "because"


@pytest.mark.parametrize(
    "text",
    [
        "no marker at all",
        "prose" + MARKER + "not json",
        "prose" + MARKER + '{"extra": 1, "rationale": "r"}',
    ],
    ids=["missing", "unreadable", "unknown key"],
)
def test_split_refuses_a_missing_or_malformed_tail(text: str) -> None:
    with pytest.raises(ValueError, match=r"tail|Expecting|extra|Extra|validation"):
        split(text)


def test_visible_never_shows_the_tail_or_a_marker_cut_short() -> None:
    assert visible("The reply") == "The reply"
    assert visible("The reply\n") == "The reply"
    assert visible("The reply\n--") == "The reply"
    assert visible("The reply" + MARKER + '{"not_found": false') == "The reply"
