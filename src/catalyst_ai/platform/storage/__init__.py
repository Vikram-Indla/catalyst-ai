"""Storage: the service's own database behind one seam; PostgreSQL live, memory in tests."""

from catalyst_ai.platform.storage.jobrows import JobRow
from catalyst_ai.platform.storage.jobs_memory import MemoryJobStore
from catalyst_ai.platform.storage.jobs_postgres import PostgresJobStore
from catalyst_ai.platform.storage.memory import MemoryStorage
from catalyst_ai.platform.storage.migrate import migrate
from catalyst_ai.platform.storage.port import JobStore, Storage
from catalyst_ai.platform.storage.postgres import PostgresStorage, StorageUnavailableError
from catalyst_ai.platform.storage.rows import (
    ChunkRow,
    DocumentRecord,
    DocumentState,
    LexicalQuery,
    RetentionCut,
    SearchScope,
    StoredHit,
)

__all__ = [
    "ChunkRow",
    "DocumentRecord",
    "DocumentState",
    "JobRow",
    "JobStore",
    "LexicalQuery",
    "MemoryJobStore",
    "MemoryStorage",
    "PostgresJobStore",
    "PostgresStorage",
    "RetentionCut",
    "SearchScope",
    "Storage",
    "StorageUnavailableError",
    "StoredHit",
    "migrate",
]
