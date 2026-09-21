"""Indexing: hashes decide re-embedding, the budget refuses, oversized documents are refused."""

import dataclasses

import pytest

from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.storage import MemoryStorage, StorageUnavailableError
from catalyst_ai.retrieval import WORK_ITEMS, Job, delete, upsert
from catalyst_ai.retrieval.ingest import INDEX_BUDGET, refuse_oversized
from tests.unit.capabilities.improve_story.conftest import FrozenClock, ScriptedProvider
from tests.unit.platform.storage.conftest import ORG_A
from tests.unit.retrieval.conftest import doc, job, seeded

LOGIN = doc("A-1", "The login button is broken on mobile", title="Login broken on mobile")
EXPORT = doc("A-2", "Export the board to CSV with every column", title="Export board")


async def test_upsert_embeds_new_documents_and_touches_unchanged_ones() -> None:
    storage, provider = await seeded()
    outcome = await upsert(job(), [LOGIN, doc("A-9", "New item")], storage, provider)
    assert [r.unchanged for r in outcome.results] == [True, False]
    assert outcome.results[1].chunks == 1
    assert outcome.index_chunks == 5
    assert len(provider.embed_calls) == 2
    assert provider.embed_calls[-1].texts == ["New item"]
    assert outcome.usage.input_tokens > 0


async def test_upsert_re_embeds_when_the_hash_or_the_version_changed() -> None:
    storage, provider = await seeded()
    changed = doc("A-1", "The login button is broken on desktop", title="Login broken on mobile")
    outcome = await upsert(job(), [changed], storage, provider)
    assert outcome.results[0].unchanged is False
    stale_job = dataclasses.replace(job(), spec=dataclasses.replace(WORK_ITEMS, revision=2))
    outcome = await upsert(stale_job, [changed], storage, provider)
    assert outcome.results[0].unchanged is False
    assert outcome.results[0].embedding_version == "d768-r2"
    assert outcome.usage.input_tokens > 0


async def test_upsert_with_nothing_changed_costs_nothing() -> None:
    storage, provider = await seeded()
    calls = len(provider.embed_calls)
    outcome = await upsert(job(), [EXPORT], storage, provider)
    assert outcome.results[0].unchanged is True
    assert outcome.usage.cost_micros == 0
    assert len(provider.embed_calls) == calls


async def test_upsert_refuses_over_the_index_budget_before_embedding() -> None:
    storage, provider = await seeded()
    calls = len(provider.embed_calls)
    with pytest.raises(Error) as caught:
        await upsert(job(max_chunks=4), [doc("A-9", "one more")], storage, provider)
    assert caught.value.code is ErrorCode.BUDGET_EXCEEDED
    assert caught.value.details[0].code == INDEX_BUDGET
    assert len(provider.embed_calls) == calls
    replaced = await upsert(job(max_chunks=4), [doc("A-1", "replacement")], storage, provider)
    assert replaced.index_chunks == 4


def test_oversized_document_is_refused() -> None:
    with pytest.raises(Error) as caught:
        refuse_oversized([doc("big", "x" * (WORK_ITEMS.max_document_chars + 1))], WORK_ITEMS)
    assert caught.value.code is ErrorCode.INDEX_DOCUMENT_TOO_LARGE
    refuse_oversized([doc("ok", "x" * WORK_ITEMS.max_document_chars)], WORK_ITEMS)


async def test_delete_returns_the_chunks_removed() -> None:
    storage, _ = await seeded()
    assert await delete(job(), ["A-1", "missing"], storage) == 1
    assert await storage.count_chunks(ORG_A, "work_items") == 3


class _BrokenStorage(MemoryStorage):
    async def count_chunks(self, organization_id: object, corpus: object) -> int:
        raise StorageUnavailableError("broken")

    async def delete_documents(
        self, organization_id: object, corpus: object, external_ids: object
    ) -> int:
        raise StorageUnavailableError("broken")


async def test_storage_failures_become_the_index_error() -> None:
    storage = _BrokenStorage(FrozenClock())
    provider = ScriptedProvider(["{}"])
    with pytest.raises(Error) as caught:
        await upsert(job(), [doc("A-1", "text")], storage, provider)
    assert caught.value.code is ErrorCode.INDEX_UNAVAILABLE
    assert caught.value.retry_after_ms == 5_000
    with pytest.raises(Error):
        await delete(Job(ORG_A, WORK_ITEMS, "search", 1, max_chunks=1), ["A-1"], storage)
