"""The table names derive from the corpus; the row values are frozen."""

import dataclasses

import pytest

from catalyst_ai.platform.storage import ChunkRow
from catalyst_ai.platform.storage.rows import chunks_table, documents_table


def test_table_names_follow_the_corpus() -> None:
    assert documents_table("work_items") == "index_documents_work_items"
    assert chunks_table("work_items") == "embeddings_work_items"


def test_rows_are_frozen() -> None:
    row = ChunkRow(0, "text", (1.0,))
    with pytest.raises(dataclasses.FrozenInstanceError):
        row.__setattr__("text", "other")
