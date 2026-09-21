"""Hybrid search: an empty corpus costs nothing; both legs run; exclusions and kinds hold."""

import dataclasses
from typing import Any

import pytest

from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.search import SearchMode
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.storage import MemoryStorage, StorageUnavailableError
from catalyst_ai.retrieval import WORK_ITEMS, Query, search
from catalyst_ai.retrieval.fusion import FUSION
from tests.unit.capabilities.improve_story.conftest import FrozenClock, ScriptedProvider
from tests.unit.platform.storage.conftest import ORG_A, ORG_B
from tests.unit.retrieval.conftest import seeded

PHRASE_QUERY = '"saved filters"'


BASE = Query(
    organization_id=ORG_A,
    spec=WORK_ITEMS,
    capability="search",
    timeout_ms=1_000,
    mode=SearchMode.SIMILAR,
    text="",
    kinds=(),
    exclude=(),
    k=10,
)


def query(text: str, mode: SearchMode = SearchMode.SIMILAR, **overrides: Any) -> Query:
    return dataclasses.replace(BASE, text=text, mode=mode, **overrides)


async def test_empty_corpus_returns_nothing_without_a_port_call() -> None:
    storage = MemoryStorage(FrozenClock())
    provider = ScriptedProvider(["{}"])
    found = await search(query("anything", organization_id=ORG_B), storage, provider)
    assert found.hits == []
    assert found.consulted is False
    assert found.usage.cost_micros == 0
    assert provider.embed_calls == []


async def test_similar_finds_the_item_by_both_legs() -> None:
    storage, provider = await seeded()
    found = await search(query("Login button broken on mobile"), storage, provider)
    assert found.hits[0].external_id == "A-1"
    assert found.hits[0].provenance.vector_rank == 1
    assert found.hits[0].provenance.lexical_rank == 1
    assert found.hits[0].title == "Login broken on mobile"
    assert found.fusion == FUSION
    assert found.embedding_version == WORK_ITEMS.version
    assert provider.embed_calls[-1].purpose == "query"
    assert found.consulted is True


async def test_query_mode_with_a_phrase_and_filters() -> None:
    storage, provider = await seeded()
    found = await search(query(PHRASE_QUERY, SearchMode.QUERY), storage, provider)
    assert found.hits[0].external_id == "A-3"
    epics = await search(query("export", kinds=("epic",)), storage, provider)
    assert {h.external_id for h in epics.hits} == {"A-4"}
    excluded = await search(query("export", exclude=("A-2", "A-4")), storage, provider)
    assert not {"A-2", "A-4"} & {h.external_id for h in excluded.hits}
    assert len((await search(query("export", k=1), storage, provider)).hits) == 1


async def test_a_query_of_stop_words_skips_the_lexical_leg() -> None:
    storage, provider = await seeded()
    found = await search(query("the and for"), storage, provider)
    assert all(h.provenance.lexical_rank is None for h in found.hits)


class _BrokenStorage(MemoryStorage):
    async def count_chunks(self, organization_id: object, corpus: object) -> int:
        raise StorageUnavailableError("broken")


async def test_storage_failure_becomes_the_index_error() -> None:
    with pytest.raises(Error) as caught:
        await search(query("x"), _BrokenStorage(FrozenClock()), ScriptedProvider(["{}"]))
    assert caught.value.code is ErrorCode.INDEX_UNAVAILABLE
