"""Doubles for retrieval: an indexing job, documents with real hashes, a seeded store."""

import hashlib

from catalyst_ai.contract.search import IndexDocument
from catalyst_ai.platform.storage import MemoryStorage
from catalyst_ai.retrieval import WORK_ITEMS, Job, upsert
from tests.unit.capabilities.improve_story.conftest import FrozenClock, ScriptedProvider
from tests.unit.platform.storage.conftest import ORG_A

TIMEOUT_MS = 5_000
MAX_CHUNKS = 1_000


def doc(
    external_id: str, text: str, *, kind: str = "story", title: str | None = None
) -> IndexDocument:
    return IndexDocument(
        external_id=external_id,
        kind=kind,
        title=title,
        text=text,
        data_class="CONFIDENTIAL",
        content_hash=hashlib.sha256(f"{title}\n{text}".encode()).hexdigest(),
    )


def job(max_chunks: int = MAX_CHUNKS) -> Job:
    return Job(ORG_A, WORK_ITEMS, "search", TIMEOUT_MS, max_chunks=max_chunks)


async def seeded() -> tuple[MemoryStorage, ScriptedProvider]:
    storage = MemoryStorage(FrozenClock())
    provider = ScriptedProvider(["{}"])
    await upsert(
        job(),
        [
            doc("A-1", "The login button is broken on mobile", title="Login broken on mobile"),
            doc("A-2", "Export the board to CSV with every column", title="Export board"),
            doc("A-3", "Members share saved filters with a team", title="Share saved filters"),
            doc("A-4", "Epic: reporting and export", kind="epic", title="Reporting"),
        ],
        storage,
        provider,
    )
    return storage, provider
