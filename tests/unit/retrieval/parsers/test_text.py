"""Plain text and Markdown parsing: paragraphs, headings as a path, fences, list items, refusals."""

import pytest

from catalyst_ai.retrieval.parsers import Reason, parse
from catalyst_ai.retrieval.parsers.port import ParserError
from catalyst_ai.retrieval.parsers.text import MAX_BYTES, decode, parse_markdown, parse_text


def test_plain_text_paragraphs() -> None:
    parsed = parse_text(b"one\nstill one\n\n\ntwo\n")
    assert [(b.heading_path, b.text) for b in parsed.blocks] == [((), "one still one"), ((), "two")]
    assert parsed.headings == []
    assert parse_text(b"").blocks == []


def test_markdown_headings_set_the_path_and_lists_split() -> None:
    text = b"# Top\n\nintro\n\n## Sub\n\n- a\n- b\n\n### Deep\n\ntext\n\n# Other\n\nlast\n"
    parsed = parse_markdown(text)
    assert [(b.heading_path, b.text) for b in parsed.blocks] == [
        (("Top",), "intro"),
        (("Top", "Sub"), "- a"),
        (("Top", "Sub"), "- b"),
        (("Top", "Sub", "Deep"), "text"),
        (("Other",), "last"),
    ]
    assert parsed.headings == ["Top", "Top > Sub", "Top > Sub > Deep", "Other"]


def test_markdown_fences_and_skipped_levels() -> None:
    text = b"### Only third\n\npara\n\n```\n# not a heading\ncode\n```\n\nafter\n"
    parsed = parse_markdown(text)
    assert parsed.blocks[0].heading_path == ("Only third",)
    assert parsed.blocks[1].text == "# not a heading code"
    assert parsed.blocks[2].text == "after"
    seven = parse_markdown(b"####### seven\n\nx\n")
    assert seven.blocks[0].heading_path == ()


def test_decode_refuses_binary_control_and_oversized() -> None:
    with pytest.raises(ParserError) as binary:
        decode(b"\xff\xfe not utf-8")
    assert binary.value.reason is Reason.MALFORMED
    with pytest.raises(ParserError) as control:
        decode(b"text\x00text")
    assert control.value.reason is Reason.MALFORMED
    with pytest.raises(ParserError) as big:
        decode(b"a" * (MAX_BYTES + 1))
    assert big.value.reason is Reason.TOO_LARGE
    assert decode(b"\xef\xbb\xbfbom\r\nline") == "bom\nline"


def test_parse_dispatch_and_unsupported() -> None:
    assert parse("text", b"x").blocks[0].text == "x"
    assert parse("markdown", b"# H\n\nx").blocks[0].heading_path == ("H",)
    with pytest.raises(ParserError) as caught:
        parse("xlsx", b"x")
    assert caught.value.reason is Reason.UNSUPPORTED
