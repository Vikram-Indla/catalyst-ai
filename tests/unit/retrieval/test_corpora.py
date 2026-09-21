"""Each corpus declares its version label from dimensions and revision."""

from catalyst_ai.retrieval import CORPORA, WORK_ITEMS, spec_of


def test_work_items_declaration() -> None:
    assert spec_of("work_items") is WORK_ITEMS
    assert WORK_ITEMS.version == "d768-r1"
    assert WORK_ITEMS.chunk_chars > WORK_ITEMS.overlap_chars
    assert set(CORPORA) == {"work_items"}
