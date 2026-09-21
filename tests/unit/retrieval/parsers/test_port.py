"""The port's values: blocks, headings, the bound, the heading clip, the error."""

import pytest

from catalyst_ai.retrieval.parsers.port import (
    MAX_BLOCKS,
    MAX_HEADING_CHARS,
    MAX_TEXT_CHARS,
    Block,
    Parsed,
    ParserError,
    Reason,
    bound,
    clip_heading,
)


def test_parsed_headings_and_chars() -> None:
    parsed = Parsed([Block(("A",), "one"), Block(("A", "B"), "two"), Block(("A",), "three")])
    assert parsed.headings == ["A", "A > B"]
    assert parsed.chars == 11
    assert Parsed().headings == []


def test_bound_refuses_too_many_blocks_or_too_much_text() -> None:
    assert bound(Parsed([Block((), "x")])).blocks[0].text == "x"
    with pytest.raises(ParserError) as many:
        bound(Parsed([Block((), "x")] * (MAX_BLOCKS + 1)))
    assert many.value.reason is Reason.TOO_LARGE
    with pytest.raises(ParserError) as big:
        bound(Parsed([Block((), "x" * (MAX_TEXT_CHARS + 1))]))
    assert big.value.reason is Reason.TOO_LARGE
    assert str(big.value) == big.value.message


def test_clip_heading_flattens_and_cuts() -> None:
    assert clip_heading("  a\n\tb  ") == "a b"
    assert len(clip_heading("h" * 500)) == MAX_HEADING_CHARS
