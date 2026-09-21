"""Chunking: paragraphs pack, long paragraphs cut at spaces with overlap, nothing empty."""

import dataclasses

from catalyst_ai.retrieval import WORK_ITEMS
from catalyst_ai.retrieval.chunking import chunk, embedding_input

SMALL = dataclasses.replace(WORK_ITEMS, chunk_chars=40, overlap_chars=8)


def test_empty_and_short_texts() -> None:
    assert chunk("   \n\n ", SMALL) == []
    assert chunk("one paragraph", SMALL) == ["one paragraph"]


def test_paragraphs_pack_until_the_window_is_full() -> None:
    text = "alpha beta\n\ngamma delta\n\n" + "e" * 36 + "\n\nzeta"
    windows = chunk(text, SMALL)
    assert windows[0] == "alpha beta\n\ngamma delta"
    assert windows[1] == "e" * 36
    assert windows[2] == "zeta"


def test_long_paragraph_is_cut_at_spaces_with_overlap() -> None:
    words = " ".join(f"w{i:02d}" for i in range(30))
    windows = chunk(words, SMALL)
    assert all(len(w) <= SMALL.chunk_chars for w in windows)
    assert windows[0].startswith("w00")
    assert windows[1][:3] in windows[0]
    assert words.split()[-1] in windows[-1]


def test_a_word_longer_than_the_window_is_cut_hard() -> None:
    windows = chunk("x" * 100, SMALL)
    assert all(0 < len(w) <= SMALL.chunk_chars for w in windows)
    assert "".join(windows).count("x") >= 100


def test_embedding_input_puts_the_title_above_the_window() -> None:
    assert embedding_input("Title ", "body") == "Title\nbody"
    assert embedding_input(None, "body") == "body"
    assert embedding_input("  ", "body") == "body"
