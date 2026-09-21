"""Passages for a question: the space prefix, chunk-level fusion, the found floor, no index."""

import dataclasses
import hashlib
from typing import Any

import pytest

from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.search import IndexDocument
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.storage import MemoryStorage, StorageUnavailableError, StoredHit
from catalyst_ai.retrieval import DOCUMENTS, Grounding, Job, Retrieved, retrieve, upsert
from catalyst_ai.retrieval.embeddings import NO_USAGE
from catalyst_ai.retrieval.grounding import SCORE_FLOOR, fuse_chunks
from tests.unit.capabilities.improve_story.conftest import FrozenClock, ScriptedProvider
from tests.unit.platform.storage.conftest import ORG_A

TIMEOUT_MS = 5_000


def _doc(key: str, text: str, kind: str = "wiki_page") -> IndexDocument:
    return IndexDocument(
        external_id=key,
        kind=kind,
        title=None,
        text=text,
        data_class="INTERNAL",
        content_hash=hashlib.sha256(text.encode()).hexdigest(),
    )


async def _seeded() -> tuple[MemoryStorage, ScriptedProvider]:
    storage = MemoryStorage(FrozenClock())
    provider = ScriptedProvider(["{}"])
    job = Job(ORG_A, DOCUMENTS, "documents", TIMEOUT_MS, max_chunks=1_000)
    documents = [
        _doc("kb/runbook", "§ Paging\nAlerts page the on-call engineer through the paging service"),
        _doc("kb/export", "§ Limits\nAn export covers at most five thousand rows", "attachment"),
        _doc("other/secret", "§ Tiers\nThe on-call engineer pages the enterprise tier"),
    ]
    await upsert(job, documents, storage, provider, lambda text, _spec: [text])
    return storage, provider


BASE = Grounding(
    organization_id=ORG_A,
    spec=DOCUMENTS,
    capability="documents",
    timeout_ms=TIMEOUT_MS,
    question="",
    prefix="kb/",
    kinds=(),
    k=4,
)


def _grounding(question: str, **overrides: Any) -> Grounding:
    return dataclasses.replace(BASE, question=question, **overrides)


async def test_only_the_space_is_read_and_passages_carry_provenance() -> None:
    storage, provider = await _seeded()
    found = await retrieve(_grounding("who pages the on-call engineer"), storage, provider)
    assert found.consulted
    assert found.found
    assert found.passages[0].chunk_id == "kb/runbook#0"
    assert all(p.chunk_id.startswith("kb/") for p in found.passages)
    passage = found.passages[0]
    assert passage.document_id == "runbook"
    assert passage.heading_path == ["Paging"]
    assert passage.text.startswith("Alerts page")
    assert passage.score >= SCORE_FLOOR


async def test_kinds_filter_and_an_empty_index_cost_nothing() -> None:
    storage, provider = await _seeded()
    filtered = await retrieve(_grounding("export rows", kinds=("wiki_page",)), storage, provider)
    assert all(p.document_id != "export" for p in filtered.passages)
    empty = await retrieve(_grounding("anything"), MemoryStorage(FrozenClock()), provider)
    assert empty == Retrieved([], NO_USAGE, "double", consulted=False)
    assert not empty.found


async def test_a_storage_failure_is_index_unavailable() -> None:
    class Broken(MemoryStorage):
        async def count_chunks(self, organization_id: object, corpus: object) -> int:
            raise StorageUnavailableError("down")

    with pytest.raises(Error) as caught:
        await retrieve(_grounding("q"), Broken(FrozenClock()), ScriptedProvider(["{}"]))
    assert caught.value.code is ErrorCode.INDEX_UNAVAILABLE


def test_fuse_chunks_ranks_by_both_legs_and_bounds_k() -> None:
    def hit(key: str, index: int) -> StoredHit:
        return StoredHit(key, "wiki_page", None, index, "§ H\ntext", "m", "v", 1.0)

    vector = [hit("kb/a", 0), hit("kb/b", 0)]
    lexical = [hit("kb/b", 0), hit("kb/c", 1)]
    fused = fuse_chunks(vector, lexical, 2)
    assert [p.chunk_id for p in fused] == ["kb/b#0", "kb/a#0"]
    assert fused[0].score > fused[1].score
    assert fuse_chunks([], [], 3) == []
