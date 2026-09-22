"""PostgresStorage: the seam over asyncpg; every call is one transaction under the tenant policy."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from types import MappingProxyType
from typing import Any
from uuid import UUID

import asyncpg
from asyncpg.pool import PoolConnectionProxy
from pgvector.asyncpg import register_vector

from catalyst_ai.contract.search import Corpus
from catalyst_ai.platform.clock import Clock
from catalyst_ai.platform.storage.rows import (
    ChunkRow,
    DocumentRecord,
    DocumentState,
    LexicalQuery,
    RetentionCut,
    SearchScope,
    StoredHit,
    chunks_table,
    documents_table,
)

QUERIES = Path(__file__).parent / "queries"
POOL_MIN = 1
LEXICAL_FILES = MappingProxyType({"any": "search_lexical_any", "web": "search_lexical_web"})
NOT_CONNECTED = "pool not connected"


class StorageUnavailableError(Exception):
    """The database did not answer; the caller degrades to the catalog's index error."""


def sql(name: str, corpus: Corpus | None = None) -> str:
    """Return one query file with its table placeholders filled for the corpus."""
    text = (QUERIES / f"{name}.sql").read_text(encoding="utf-8")
    if corpus is not None:
        text = text.replace("{documents}", documents_table(corpus)).replace(
            "{chunks}", chunks_table(corpus)
        )
    return text


async def _prepare_connection(connection: asyncpg.Connection[Any]) -> None:
    await register_vector(connection)
    await connection.execute(sql("session_role_app"))


class PostgresStorage:
    """A pool whose connections run as the application role; the tenant is set per transaction."""

    def __init__(self, dsn: str, clock: Clock, pool_max: int, command_timeout_s: float) -> None:
        """Bind the connection string and the limits; `connect` opens the pool."""
        self._dsn = dsn
        self._clock = clock
        self._pool_max = pool_max
        self._command_timeout_s = command_timeout_s
        self._pool: asyncpg.Pool[Any] | None = None

    async def connect(self) -> None:
        """Open the pool; a database that does not answer is a startup failure."""
        try:
            self._pool = await asyncpg.create_pool(
                self._dsn,
                min_size=POOL_MIN,
                max_size=self._pool_max,
                command_timeout=self._command_timeout_s,
                init=_prepare_connection,
            )
        except (OSError, asyncpg.PostgresError) as error:
            raise StorageUnavailableError(str(type(error).__name__)) from error

    async def close(self) -> None:
        """Close the pool."""
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    @asynccontextmanager
    async def _tenant(self, organization_id: UUID) -> AsyncIterator[PoolConnectionProxy[Any]]:
        if self._pool is None:
            raise StorageUnavailableError(NOT_CONNECTED)
        try:
            async with self._pool.acquire() as connection, connection.transaction():
                await connection.execute(sql("session_organization"), str(organization_id))
                yield connection
        except (OSError, asyncpg.PostgresError) as error:
            raise StorageUnavailableError(str(type(error).__name__)) from error

    async def ready(self) -> bool:
        """Return whether a trivial query answers."""
        if self._pool is None:
            return False
        try:
            async with self._pool.acquire() as connection:
                await connection.fetchval(sql("ready"))
        except (OSError, asyncpg.PostgresError):
            return False
        return True

    async def document_states(
        self, organization_id: UUID, corpus: Corpus, external_ids: list[str]
    ) -> dict[str, DocumentState]:
        """Return the state of every key the index holds."""
        async with self._tenant(organization_id) as connection:
            rows = await connection.fetch(
                sql("document_states", corpus), organization_id, external_ids
            )
        return {
            row["external_id"]: DocumentState(
                row["external_id"],
                row["content_hash"],
                row["embedding_model"],
                row["embedding_version"],
                row["chunks"],
            )
            for row in rows
        }

    async def replace_document(self, document: DocumentRecord, chunks: list[ChunkRow]) -> None:
        """Delete the key, insert the document row, insert its chunks — one transaction."""
        corpus = document.corpus
        async with self._tenant(document.organization_id) as connection:
            await connection.fetch(
                sql("document_delete", corpus), document.organization_id, [document.external_id]
            )
            document_id = await connection.fetchval(
                sql("document_insert", corpus),
                document.organization_id,
                document.external_id,
                document.kind,
                document.title,
                document.text,
                document.content_hash,
                document.data_class,
                document.embedding_model,
                document.embedding_version,
                len(chunks),
                self._clock.now(),
            )
            await connection.executemany(
                sql("chunk_insert", corpus),
                [
                    (
                        document.organization_id,
                        document_id,
                        document.external_id,
                        document.kind,
                        document.title,
                        chunk.chunk_index,
                        chunk.text,
                        list(chunk.embedding),
                        document.embedding_model,
                        document.embedding_version,
                    )
                    for chunk in chunks
                ],
            )

    async def touch_document(self, organization_id: UUID, corpus: Corpus, external_id: str) -> None:
        """Stamp the key as seen now."""
        async with self._tenant(organization_id) as connection:
            await connection.execute(
                sql("document_touch", corpus), organization_id, external_id, self._clock.now()
            )

    async def read_document(
        self, organization_id: UUID, corpus: Corpus, external_id: str
    ) -> DocumentRecord | None:
        """Return the stored document or None."""
        async with self._tenant(organization_id) as connection:
            row = await connection.fetchrow(
                sql("document_read", corpus), organization_id, external_id
            )
        if row is None:
            return None
        return DocumentRecord(
            organization_id=organization_id,
            corpus=corpus,
            external_id=row["external_id"],
            kind=row["kind"],
            title=row["title"],
            text=row["text"],
            content_hash=row["content_hash"],
            data_class=row["data_class"],
            embedding_model=row["embedding_model"],
            embedding_version=row["embedding_version"],
        )

    async def delete_documents(
        self, organization_id: UUID, corpus: Corpus, external_ids: list[str]
    ) -> int:
        """Forget the keys; the chunks go with them by cascade."""
        async with self._tenant(organization_id) as connection:
            rows = await connection.fetch(
                sql("document_delete", corpus), organization_id, external_ids
            )
        return sum(int(row["chunks"]) for row in rows)

    async def count_chunks(self, organization_id: UUID, corpus: Corpus) -> int:
        """Return the organisation's chunk count."""
        async with self._tenant(organization_id) as connection:
            value = await connection.fetchval(sql("chunks_count", corpus), organization_id)
        return int(value or 0)

    async def search_vector(
        self, scope: SearchScope, vector: tuple[float, ...], model: str, version: str
    ) -> list[StoredHit]:
        """Nearest chunks by cosine distance over the HNSW index, filtered before the limit."""
        async with self._tenant(scope.organization_id) as connection:
            await connection.execute(sql("session_search_settings"))
            rows = await connection.fetch(
                sql("search_vector", scope.corpus),
                scope.organization_id,
                list(vector),
                model,
                version,
                list(scope.kinds),
                list(scope.exclude),
                scope.limit,
                scope.prefix,
            )
        return _hits(rows)

    async def search_lexical(self, scope: SearchScope, query: LexicalQuery) -> list[StoredHit]:
        """Chunks the text search ranks highest for the query form."""
        async with self._tenant(scope.organization_id) as connection:
            rows = await connection.fetch(
                sql(LEXICAL_FILES[query.form], scope.corpus),
                scope.organization_id,
                query.text,
                list(scope.kinds),
                list(scope.exclude),
                scope.limit,
                scope.prefix,
            )
        return _hits(rows)

    async def organizations(self, corpus: Corpus) -> list[UUID]:
        """Every organisation with documents, read under the maintenance role."""
        if self._pool is None:
            raise StorageUnavailableError(NOT_CONNECTED)
        try:
            async with self._pool.acquire() as connection:
                await connection.execute(sql("session_role_maintenance"))
                try:
                    rows = await connection.fetch(sql("organizations", corpus))
                finally:
                    await connection.execute(sql("session_role_app"))
        except (OSError, asyncpg.PostgresError) as error:
            raise StorageUnavailableError(str(type(error).__name__)) from error
        return [UUID(str(row["organization_id"])) for row in rows]

    async def stale_documents(
        self, organization_id: UUID, corpus: Corpus, model: str, version: str, limit: int
    ) -> list[str]:
        """Keys not embedded at the model and version."""
        async with self._tenant(organization_id) as connection:
            rows = await connection.fetch(
                sql("documents_stale", corpus), organization_id, model, version, limit
            )
        return [str(row["external_id"]) for row in rows]

    async def expired_documents(self, cut: RetentionCut) -> list[str]:
        """Keys last seen before the cut."""
        async with self._tenant(cut.organization_id) as connection:
            rows = await connection.fetch(
                sql("documents_expired", cut.corpus), cut.organization_id, cut.before, cut.limit
            )
        return [str(row["external_id"]) for row in rows]

    async def remember_nonce(self, nonce: str, expires_at: int, now: int) -> bool:
        """Platform state, no tenant: forget the expired, insert once, refuse the second time."""
        if self._pool is None:
            raise StorageUnavailableError(NOT_CONNECTED)
        try:
            async with self._pool.acquire() as connection, connection.transaction():
                await connection.execute(sql("nonce_forget"), now)
                inserted = await connection.fetchval(sql("nonce_remember"), nonce, expires_at)
        except (OSError, asyncpg.PostgresError) as error:
            raise StorageUnavailableError(str(type(error).__name__)) from error
        return inserted is not None


def _hits(rows: Sequence[asyncpg.Record]) -> list[StoredHit]:
    return [
        StoredHit(
            external_id=row["external_id"],
            kind=row["kind"],
            title=row["title"],
            chunk_index=int(row["chunk_index"]),
            text=row["text"],
            embedding_model=row["embedding_model"],
            embedding_version=row["embedding_version"],
            score=float(row["score"]),
        )
        for row in rows
    ]
