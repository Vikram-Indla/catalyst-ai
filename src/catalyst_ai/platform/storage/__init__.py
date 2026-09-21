"""Storage: the service's own database behind one seam; PostgreSQL live, memory in tests."""

from catalyst_ai.platform.storage.memory import MemoryStorage
from catalyst_ai.platform.storage.migrate import migrate
from catalyst_ai.platform.storage.port import Storage
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
    "LexicalQuery",
    "MemoryStorage",
    "PostgresStorage",
    "RetentionCut",
    "SearchScope",
    "Storage",
    "StorageUnavailableError",
    "StoredHit",
    "migrate",
]
