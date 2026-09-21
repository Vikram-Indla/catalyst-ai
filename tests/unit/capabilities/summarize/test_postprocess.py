"""Stage 7 rules: the participant check, the word cap, structure stripping, confidence."""

import pytest

from catalyst_ai.capabilities.summarize.postprocess import (
    cap_words,
    check_participants,
    confidence,
    covered_range,
    strip_structure,
    tokens_in,
    word_count,
)
from catalyst_ai.capabilities.summarize.schema import ModelOutput
from catalyst_ai.platform.errors import Error
from tests.unit.capabilities.summarize.conftest import make_request


def test_tokens_and_words() -> None:
    assert tokens_in("p1 said, p12 agreed; pineapple") == {"p1", "p12"}
    assert word_count("one two  three\nfour") == 4


def test_check_participants_accepts_thread_and_status_tokens_only() -> None:
    request = make_request(
        status_changes=[
            {
                "participant": "p4",
                "from_status": None,
                "to_status": "Done",
                "at": "2026-09-01T10:00:00+00:00",
            }
        ]
    )
    check_participants("p1 and p4 moved it", ["p1"], request)
    with pytest.raises(Error):
        check_participants("p7 said so", [], request)
    with pytest.raises(Error):
        check_participants("fine", ["p8"], request)


def test_cap_words_cuts_and_marks() -> None:
    assert cap_words("a b c", 5) == "a b c"
    assert cap_words("a b c d e f", 3) == "a b c …"


def test_strip_structure_removes_headings_and_fences() -> None:
    assert strip_structure("# Title\n\ntext\n```\ncode\n```") == "Title\n\ntext\n\ncode\n"


def test_covered_range_and_confidence() -> None:
    request = make_request(target_words=40)
    assert covered_range(request).count == 4
    assert covered_range(make_request(items=[])).first_id is None
    output = ModelOutput(summary="## x\n" + "w " * 100, participants_mentioned=[], rationale="r")
    assert confidence("w " * 100, output, request) == 0.6
    assert (
        confidence(
            "short", ModelOutput(summary="short", participants_mentioned=[], rationale="r"), request
        )
        == 1.0
    )
