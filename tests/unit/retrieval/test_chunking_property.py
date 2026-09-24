"""Properties of chunking: bounded windows, full word coverage, determinism, order."""

import dataclasses
import re

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from catalyst_ai.retrieval import WORK_ITEMS
from catalyst_ai.retrieval.chunking import chunk
from tests.conftest import examples

SPEC = dataclasses.replace(WORK_ITEMS, chunk_chars=60, overlap_chars=10)
WORD = re.compile(r"\S+")
VOCABULARY = [f"w{i}é" if i % 5 else f"word{i}" for i in range(60)] + ["x" * 40, "a", "PRJ-42"]
words = st.sampled_from(VOCABULARY)


def _join(items: list[str]) -> str:
    return " ".join(w if i % 7 else w + "\n\n" for i, w in enumerate(items))


texts = st.lists(words, min_size=0, max_size=24).map(_join)
unique_texts = st.lists(words, min_size=0, max_size=24, unique=True).map(_join)
SLOW = [HealthCheck.too_slow]


@settings(max_examples=examples(150), suppress_health_check=SLOW, deadline=None)
@given(texts)
def test_windows_are_bounded_non_empty_and_cover_every_word(text: str) -> None:
    windows = chunk(text, SPEC)
    assert all(0 < len(w) <= SPEC.chunk_chars for w in windows)
    assert set(WORD.findall(text)) <= set(WORD.findall(" ".join(windows)))
    assert chunk(text, SPEC) == windows


@settings(max_examples=examples(100), suppress_health_check=SLOW, deadline=None)
@given(unique_texts)
def test_windows_keep_the_order_of_the_text(text: str) -> None:
    order = {word: i for i, word in enumerate(WORD.findall(text))}
    windows = chunk(text, SPEC)
    firsts = [WORD.findall(w)[0] for w in windows if WORD.findall(w)]
    positions = [order[first] for first in firsts if first in order]
    assert positions == sorted(positions)
