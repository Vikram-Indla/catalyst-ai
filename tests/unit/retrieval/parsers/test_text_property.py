"""Properties of the text parsers: never a crash, every word kept, headings bounded, determinism."""

import re

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from catalyst_ai.retrieval.parsers.port import MAX_DEPTH
from catalyst_ai.retrieval.parsers.text import parse_markdown, parse_text

WORD = re.compile(r"\S+")
VOCABULARY = ["alpha", "beta", "gamma", "PRJ-42", "x" * 30, "é", "-", "1."]
tokens = st.sampled_from([*VOCABULARY, "\n", "\n\n", "# ", "## ", "### ", "```\n", "  "])
texts = st.lists(tokens, min_size=0, max_size=40).map("".join)
SLOW = [HealthCheck.too_slow]


@settings(max_examples=150, suppress_health_check=SLOW, deadline=None)
@given(texts)
def test_plain_text_keeps_every_word_in_order(text: str) -> None:
    parsed = parse_text(text.encode())
    kept = [w for block in parsed.blocks for w in WORD.findall(block.text)]
    assert kept == WORD.findall(text)
    assert all(block.heading_path == () for block in parsed.blocks)


@settings(max_examples=150, suppress_health_check=SLOW, deadline=None)
@given(texts)
def test_markdown_paths_are_bounded_and_parsing_is_deterministic(text: str) -> None:
    first = parse_markdown(text.encode())
    second = parse_markdown(text.encode())
    assert first == second
    for block in first.blocks:
        assert len(block.heading_path) <= MAX_DEPTH
        assert block.text.strip() == block.text
        assert block.text
