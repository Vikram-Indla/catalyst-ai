"""The jobs: re-embed brings stale documents to the current version; retention forgets old ones."""

import dataclasses
from datetime import timedelta
from uuid import UUID

import pytest

from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.search import Corpus
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.storage import MemoryStorage, StorageUnavailableError
from catalyst_ai.retrieval import WORK_ITEMS, reembed, retention, upsert
from tests.unit.capabilities.improve_story.conftest import FrozenClock, ScriptedProvider
from tests.unit.platform.storage.conftest import ORG_A, ORG_B
from tests.unit.retrieval.conftest import doc, job, seeded


async def test_reembed_updates_every_stale_document_in_every_organisation() -> None:
    storage, provider = await seeded()
    other = dataclasses.replace(job(), organization_id=ORG_B)
    await upsert(other, [doc("B-1", "other tenant")], storage, provider)
    next_revision = dataclasses.replace(WORK_ITEMS, revision=2)
    report = await reembed(next_revision, storage, provider)
    assert (report.organizations, report.documents) == (2, 5)
    assert await storage.stale_documents(ORG_A, "work_items", "double", "d768-r2", 10) == []
    again = await reembed(next_revision, storage, provider)
    assert again.documents == 0


async def test_retention_forgets_documents_unseen_past_the_ttl() -> None:
    clock = FrozenClock()
    storage = MemoryStorage(clock)
    provider = ScriptedProvider(["{}"])
    await upsert(job(), [doc("A-1", "old")], storage, provider)
    clock.at += timedelta(days=10)
    await upsert(job(), [doc("A-2", "fresh")], storage, provider)
    report = await retention(WORK_ITEMS, storage, clock, ttl_days=5)
    assert (report.organizations, report.documents) == (1, 1)
    assert await storage.read_document(ORG_A, "work_items", "A-1") is None
    assert await storage.read_document(ORG_A, "work_items", "A-2") is not None


class _BrokenStorage(MemoryStorage):
    async def organizations(self, corpus: Corpus) -> list[UUID]:
        raise StorageUnavailableError("broken")


async def test_jobs_report_the_index_error() -> None:
    storage = _BrokenStorage(FrozenClock())
    with pytest.raises(Error) as caught:
        await reembed(WORK_ITEMS, storage, ScriptedProvider(["{}"]))
    assert caught.value.code is ErrorCode.INDEX_UNAVAILABLE
    with pytest.raises(Error):
        await retention(WORK_ITEMS, storage, FrozenClock(), 1)
