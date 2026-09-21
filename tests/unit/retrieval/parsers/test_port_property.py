"""Properties of the port: headings are distinct and ordered; the bound is exactly the limit."""

from hypothesis import given
from hypothesis import strategies as st

from catalyst_ai.retrieval.parsers.port import Block, Parsed, clip_heading

paths = st.lists(st.sampled_from(["a", "b", "c"]), min_size=0, max_size=3).map(tuple)
blocks = st.lists(st.builds(Block, paths, st.text(min_size=1, max_size=10)), max_size=20)


@given(blocks)
def test_headings_are_distinct_in_first_appearance_order(items: list[Block]) -> None:
    parsed = Parsed(items)
    headings = parsed.headings
    assert len(headings) == len(set(headings))
    seen = [" > ".join(b.heading_path) for b in items if b.heading_path]
    assert headings == list(dict.fromkeys(seen))
    assert parsed.chars == sum(len(b.text) for b in items)


@given(st.text(max_size=400))
def test_clip_heading_is_single_line_and_bounded(text: str) -> None:
    clipped = clip_heading(text)
    assert "\n" not in clipped
    assert len(clipped) <= 200
    assert clipped == clip_heading(clipped) or len(clipped) == 200
