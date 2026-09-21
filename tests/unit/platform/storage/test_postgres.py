"""The pure parts of PostgresStorage: query loading, placeholders, the unconnected refusals."""

import pytest

from catalyst_ai.platform.storage import PostgresStorage, StorageUnavailableError
from catalyst_ai.platform.storage.postgres import QUERIES, sql
from tests.unit.capabilities.improve_story.conftest import FrozenClock
from tests.unit.platform.storage.conftest import ORG_A


def test_sql_fills_the_table_placeholders_for_the_corpus() -> None:
    text = sql("search_vector", "work_items")
    assert "embeddings_work_items" in text
    assert "{chunks}" not in text
    assert "SELECT set_config" in sql("session_organization")


def test_every_query_file_is_one_statement_or_session_settings() -> None:
    for path in QUERIES.glob("*.sql"):
        statements = [s for s in path.read_text(encoding="utf-8").split(";") if s.strip()]
        assert len(statements) == 1 or path.stem == "session_search_settings", path.name


async def test_unconnected_storage_refuses_and_is_not_ready() -> None:
    storage = PostgresStorage("postgresql://u:p@h/d", FrozenClock(), 2, 1.0)
    assert await storage.ready() is False
    with pytest.raises(StorageUnavailableError):
        await storage.count_chunks(ORG_A, "work_items")
    with pytest.raises(StorageUnavailableError):
        await storage.organizations("work_items")
    await storage.close()
