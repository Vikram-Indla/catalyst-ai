"""MemoryStorage: tenancy by construction, both search legs, states, the jobs' queries."""

from datetime import timedelta

from catalyst_ai.platform.storage import LexicalQuery, MemoryStorage, RetentionCut, SearchScope
from catalyst_ai.platform.storage.memory import cosine, lexical_score
from tests.unit.capabilities.improve_story.conftest import FrozenClock, hashed_vector
from tests.unit.platform.storage.conftest import MODEL, ORG_A, ORG_B, VERSION, chunks, document


async def _seeded() -> tuple[MemoryStorage, FrozenClock]:
    clock = FrozenClock()
    storage = MemoryStorage(clock)
    await storage.replace_document(
        document(ORG_A, "A-1", "login button broken on mobile", title="Login broken"),
        chunks("login button broken on mobile"),
    )
    await storage.replace_document(
        document(ORG_A, "A-2", "export the board to csv", kind="epic"),
        chunks("export the board to csv", "second chunk about exports"),
    )
    await storage.replace_document(
        document(ORG_B, "B-1", "login button broken on mobile"),
        chunks("login button broken on mobile"),
    )
    return storage, clock


def test_cosine_and_lexical_scores() -> None:
    assert cosine((1.0, 0.0), (1.0, 0.0)) == 1.0
    assert cosine((0.0, 0.0), (1.0, 0.0)) == 0.0
    assert lexical_score(LexicalQuery("any", "'login' | 'csv'"), None, "login page") == 0.5
    assert lexical_score(LexicalQuery("any", ""), None, "login page") == 0.0
    assert (
        lexical_score(LexicalQuery("web", '"login button" mobile'), None, "login button mobile") > 1
    )
    assert lexical_score(LexicalQuery("web", '"login page"'), None, "login button") == 0.0
    assert lexical_score(LexicalQuery("web", "login csv"), None, "login button") == 0.0


async def test_search_never_crosses_the_organisation() -> None:
    storage, _ = await _seeded()
    scope = SearchScope(ORG_A, "work_items", (), (), 10)
    vector = tuple(hashed_vector("login button broken on mobile"))
    hits = await storage.search_vector(scope, vector, MODEL, VERSION)
    assert hits[0].external_id == "A-1"
    assert all(h.external_id.startswith("A-") for h in hits)
    lexical = await storage.search_lexical(scope, LexicalQuery("any", "'login'"))
    assert [h.external_id for h in lexical] == ["A-1"]
    assert await storage.count_chunks(ORG_A, "work_items") == 3
    assert await storage.count_chunks(ORG_B, "work_items") == 1


async def test_filters_kinds_excludes_and_versions() -> None:
    storage, _ = await _seeded()
    vector = tuple(hashed_vector("export"))
    only_epics = SearchScope(ORG_A, "work_items", ("epic",), (), 10)
    assert {
        h.external_id for h in await storage.search_vector(only_epics, vector, MODEL, VERSION)
    } == {"A-2"}
    excluded = SearchScope(ORG_A, "work_items", (), ("A-2",), 10)
    assert {
        h.external_id for h in await storage.search_vector(excluded, vector, MODEL, VERSION)
    } == {"A-1"}
    scope = SearchScope(ORG_A, "work_items", (), (), 10)
    assert await storage.search_vector(scope, vector, MODEL, "d64-r2") == []
    assert (
        len(
            await storage.search_vector(
                SearchScope(ORG_A, "work_items", (), (), 1), vector, MODEL, VERSION
            )
        )
        == 1
    )


async def test_states_read_touch_delete() -> None:
    storage, clock = await _seeded()
    states = await storage.document_states(ORG_A, "work_items", ["A-1", "A-2", "missing"])
    assert set(states) == {"A-1", "A-2"}
    assert states["A-2"].chunks == 2
    record = await storage.read_document(ORG_A, "work_items", "A-1")
    assert record is not None
    assert record.title == "Login broken"
    assert await storage.read_document(ORG_B, "work_items", "A-1") is None
    clock.at += timedelta(days=1)
    await storage.touch_document(ORG_A, "work_items", "A-1")
    cut = RetentionCut(ORG_A, "work_items", clock.at - timedelta(hours=1), 10)
    assert await storage.expired_documents(cut) == ["A-2"]
    assert await storage.delete_documents(ORG_A, "work_items", ["A-2", "missing"]) == 2
    assert await storage.count_chunks(ORG_A, "work_items") == 1
    assert await storage.ready() is True


async def test_organizations_and_stale_documents() -> None:
    storage, _ = await _seeded()
    await storage.replace_document(
        document(ORG_A, "A-3", "old embedding", embedding_version="d64-r0"),
        chunks("old embedding"),
    )
    assert await storage.organizations("work_items") == sorted([ORG_A, ORG_B])
    assert await storage.stale_documents(ORG_A, "work_items", MODEL, VERSION, 10) == ["A-3"]
    assert await storage.stale_documents(ORG_A, "work_items", "other", VERSION, 1) == ["A-1"]
