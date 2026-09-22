"""PostgresStorage against a real database: the seam's contract, and RLS with the layer bypassed."""

from datetime import timedelta
from uuid import UUID, uuid4

import asyncpg
import pytest

from catalyst_ai.platform.storage import (
    ChunkRow,
    LexicalQuery,
    PostgresStorage,
    RetentionCut,
    SearchScope,
    migrate,
)
from catalyst_ai.platform.storage.postgres import sql
from tests.storage.conftest import migrations_dir
from tests.unit.capabilities.improve_story.conftest import hashed_vector
from tests.unit.platform.storage.conftest import MODEL, VERSION, document

pytestmark = pytest.mark.enable_socket
DIMENSIONS = 768
RAW_SELECT = "SELECT external_id FROM embeddings_work_items"
RAW_INSERT = (
    "INSERT INTO index_documents_work_items (organization_id, external_id, kind, text,"
    " content_hash, data_class, embedding_model, embedding_version, chunks, last_seen_at)"
    " VALUES ($1, 'X', 'story', 't', 'h', 'PUBLIC', 'm', 'v', 0, now())"
)


def wide(*texts: str) -> list[ChunkRow]:
    return [
        ChunkRow(i, text, tuple(hashed_vector(text, DIMENSIONS))) for i, text in enumerate(texts)
    ]


async def _seed(storage: PostgresStorage) -> tuple[UUID, UUID]:
    a, b = uuid4(), uuid4()
    await storage.replace_document(
        document(a, "A-1", "login button broken on mobile", title="Login broken"),
        wide("login button broken on mobile"),
    )
    await storage.replace_document(
        document(a, "A-2", "export the board to csv", kind="epic"),
        wide("export the board to csv", "second chunk about exports"),
    )
    await storage.replace_document(
        document(b, "B-1", "login button broken on mobile"),
        wide("login button broken on mobile"),
    )
    return a, b


async def _cleanup(storage: PostgresStorage, a: UUID, b: UUID) -> None:
    await storage.delete_documents(a, "work_items", ["A-1", "A-2"])
    await storage.delete_documents(b, "work_items", ["B-1"])


async def test_seam_contract_end_to_end(storage: PostgresStorage) -> None:
    a, b = await _seed(storage)
    assert await storage.ready() is True
    assert await storage.count_chunks(a, "work_items") == 3
    scope = SearchScope(a, "work_items", (), (), 10)
    login = tuple(hashed_vector("login button broken on mobile", DIMENSIONS))
    hits = await storage.search_vector(scope, login, MODEL, VERSION)
    assert hits[0].external_id == "A-1"
    assert all(h.external_id.startswith("A-") for h in hits)
    assert await storage.search_vector(scope, login, MODEL, "other") == []
    lexical = await storage.search_lexical(scope, LexicalQuery("any", "'login' | 'csv'"))
    assert {h.external_id for h in lexical} == {"A-1", "A-2"}
    web = await storage.search_lexical(scope, LexicalQuery("web", '"login button"'))
    assert [h.external_id for h in web] == ["A-1"]
    epics = SearchScope(a, "work_items", ("epic",), (), 10)
    by_kind = await storage.search_lexical(epics, LexicalQuery("any", "'export'"))
    assert {h.external_id for h in by_kind} == {"A-2"}
    states = await storage.document_states(a, "work_items", ["A-1", "A-2", "zz"])
    assert states["A-2"].chunks == 2
    record = await storage.read_document(a, "work_items", "A-1")
    assert record is not None
    assert record.title == "Login broken"
    assert {a, b} <= set(await storage.organizations("work_items"))
    assert await storage.stale_documents(a, "work_items", "next", VERSION, 10) == ["A-1", "A-2"]
    await storage.touch_document(a, "work_items", "A-1")
    cut = RetentionCut(a, "work_items", storage._clock.now() + timedelta(seconds=1), 10)
    assert set(await storage.expired_documents(cut)) == {"A-1", "A-2"}
    assert await storage.delete_documents(a, "work_items", ["A-1", "A-2"]) == 3
    assert await storage.delete_documents(b, "work_items", ["B-1"]) == 1


async def test_rls_holds_with_the_application_layer_bypassed(
    storage: PostgresStorage, database_url: str
) -> None:
    a, b = await _seed(storage)
    connection = await asyncpg.connect(database_url, timeout=5)
    try:
        await connection.execute(sql("session_role_app"))
        async with connection.transaction():
            await connection.execute(sql("session_organization"), str(b))
            rows = await connection.fetch(RAW_SELECT)
            assert [r["external_id"] for r in rows] == ["B-1"]
            with pytest.raises(asyncpg.InsufficientPrivilegeError):
                await connection.execute(RAW_INSERT, a)
        async with connection.transaction():
            assert await connection.fetch(RAW_SELECT) == []
        await connection.execute(sql("session_role_maintenance"))
        assert len(await connection.fetch(RAW_SELECT)) >= 4
    finally:
        await connection.close()
    await _cleanup(storage, a, b)


async def test_migrate_is_idempotent(storage: PostgresStorage, database_url: str) -> None:
    assert await storage.ready() is True
    assert await migrate(database_url, migrations_dir()) == []


DOCUMENTS_SELECT = "SELECT external_id FROM embeddings_documents"


async def _seed_documents(storage: PostgresStorage, a: UUID, b: UUID) -> None:
    for organization, key, text in (
        (a, "kb/runbook", "§ Paging\nalerts page the on-call engineer"),
        (a, "other/secret", "§ Tiers\nthe on-call engineer pages the enterprise tier"),
        (b, "kb/theirs", "alerts page the on-call engineer"),
    ):
        record = document(organization, key, text, corpus="documents", kind="wiki_page")
        await storage.replace_document(record, wide(text))


async def _raw_rows_as(database_url: str, organization: UUID) -> list[str]:
    connection = await asyncpg.connect(database_url, timeout=5)
    try:
        await connection.execute(sql("session_role_app"))
        async with connection.transaction():
            await connection.execute(sql("session_organization"), str(organization))
            rows = await connection.fetch(DOCUMENTS_SELECT)
        async with connection.transaction():
            assert await connection.fetch(DOCUMENTS_SELECT) == []
    finally:
        await connection.close()
    return [r["external_id"] for r in rows]


async def test_documents_corpus_holds_rls_and_the_space_prefix(
    storage: PostgresStorage, database_url: str
) -> None:
    a, b = uuid4(), uuid4()
    await _seed_documents(storage, a, b)
    scoped = SearchScope(a, "documents", (), (), 10, "kb/")
    vector = tuple(hashed_vector("on-call engineer", DIMENSIONS))
    hits = await storage.search_vector(scoped, vector, MODEL, VERSION)
    assert [h.external_id for h in hits] == ["kb/runbook"]
    lexical = await storage.search_lexical(scoped, LexicalQuery("web", "on-call engineer"))
    assert [h.external_id for h in lexical] == ["kb/runbook"]
    unscoped = SearchScope(a, "documents", (), (), 10)
    everything = await storage.search_vector(unscoped, vector, MODEL, VERSION)
    assert {h.external_id for h in everything} == {"kb/runbook", "other/secret"}
    assert await _raw_rows_as(database_url, b) == ["kb/theirs"]
    await storage.delete_documents(a, "documents", ["kb/runbook", "other/secret"])
    await storage.delete_documents(b, "documents", ["kb/theirs"])


async def test_a_nonce_is_remembered_once_and_forgotten_when_it_expires(
    storage: PostgresStorage,
) -> None:
    nonce = f"n-{uuid4()}"
    assert await storage.remember_nonce(nonce, expires_at=1_000, now=900) is True
    assert await storage.remember_nonce(nonce, expires_at=1_000, now=950) is False
    assert await storage.remember_nonce(nonce, expires_at=1_000, now=999) is False
    assert await storage.remember_nonce(nonce, expires_at=2_000, now=1_000) is True
