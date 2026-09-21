"""Documents in the index: keys per space, structured windows led by the path, passages back."""

import dataclasses

from catalyst_ai.retrieval import DOCUMENTS, chunk_id, document_key, space_prefix, windows_of
from catalyst_ai.retrieval.documents import passage_of, split_window
from catalyst_ai.retrieval.parsers import Block, Parsed

SPEC = dataclasses.replace(DOCUMENTS, chunk_chars=60, overlap_chars=10)


def test_keys_ids_and_prefix() -> None:
    assert document_key("kb", "doc-1") == "kb/doc-1"
    assert space_prefix("kb") == "kb/"
    assert chunk_id("kb/doc-1", 3) == "kb/doc-1#3"
    assert document_key("kb", "doc-1").startswith(space_prefix("kb"))


def test_windows_group_by_heading_path_and_lead_with_it() -> None:
    parsed = Parsed(
        [
            Block(("A",), "one"),
            Block(("A",), "two"),
            Block(("A", "B"), "three"),
            Block((), "loose"),
            Block(("A",), "back"),
        ]
    )
    windows = windows_of(parsed, SPEC)
    assert windows == ["§ A\none\n\ntwo", "§ A > B\nthree", "loose", "§ A\nback"]
    long = Parsed([Block(("H",), "word " * 40)])
    cut = windows_of(long, SPEC)
    assert len(cut) > 1
    assert all(w.startswith("§ H\n") for w in cut)
    assert windows_of(Parsed(), SPEC) == []


def test_split_window_and_passage_of() -> None:
    assert split_window("§ A > B\ntext") == (["A", "B"], "text")
    assert split_window("plain") == ([], "plain")
    passage = passage_of("kb/doc-1", 2, "§ A\nbody", 0.5)
    assert passage.chunk_id == "kb/doc-1#2"
    assert passage.document_id == "doc-1"
    assert passage.heading_path == ["A"]
    assert passage.text == "body"
    assert passage_of("nokey", 0, "t", 0.1).document_id == "nokey"
