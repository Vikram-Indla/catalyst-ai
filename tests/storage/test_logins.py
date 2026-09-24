"""Three logins on a real PostgreSQL: serve cannot become maintenance; a missing vector stops migrate."""

from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import asyncpg
import pytest

from catalyst_ai.platform.storage import PostgresStorage, migrate
from catalyst_ai.platform.storage.jobs_postgres import PostgresJobStore
from catalyst_ai.platform.storage.migrate import VECTOR_MISSING, ExtensionMissingError
from catalyst_ai.platform.storage.postgres import StorageUnavailableError, sql
from tests.conftest import REPO_ROOT
from tests.storage.conftest import COMMAND_TIMEOUT_S, migrations_dir
from tests.unit.capabilities.improve_story.conftest import FrozenClock
from tools import rules
from tools.evalkit import provision

pytestmark = pytest.mark.enable_socket
LOGINS = "logins.sql"
THROWAWAY = "for-this-test-only"


def _as(url: str, user: str, database: str | None = None) -> str:
    parts = urlsplit(url)
    host = parts.netloc.rsplit("@", 1)[1]
    path = f"/{database}" if database else parts.path
    return urlunsplit((parts.scheme, f"{user}:{THROWAWAY}@{host}", path, "", ""))


async def _logins(database_url: str) -> None:
    await provision(database_url, REPO_ROOT, LOGINS)
    owner = await asyncpg.connect(database_url)
    try:
        for login in ("catalyst_ai_serve", "catalyst_ai_worker"):
            await owner.execute(f"ALTER ROLE {login} PASSWORD '{THROWAWAY}'")
    finally:
        await owner.close()


async def test_serve_cannot_become_maintenance_and_the_worker_can(
    storage: PostgresStorage, database_url: str
) -> None:
    await _logins(database_url)
    serve = await asyncpg.connect(_as(database_url, "catalyst_ai_serve"))
    try:
        await serve.execute("SET ROLE catalyst_ai_app")
        with pytest.raises(asyncpg.InsufficientPrivilegeError):
            await serve.execute("SET ROLE catalyst_ai_maintenance")
    finally:
        await serve.close()
    worker = await asyncpg.connect(_as(database_url, "catalyst_ai_worker"))
    try:
        await worker.execute("SET ROLE catalyst_ai_maintenance")
    finally:
        await worker.close()


async def test_serve_reads_its_tenant_but_never_counts_every_organisation(
    storage: PostgresStorage, database_url: str
) -> None:
    await _logins(database_url)
    served = PostgresStorage(
        _as(database_url, "catalyst_ai_serve"), FrozenClock(), 2, COMMAND_TIMEOUT_S
    )
    await served.connect()
    try:
        jobs = PostgresJobStore(served)
        assert await jobs.read_job(uuid4(), uuid4()) is None
        with pytest.raises(StorageUnavailableError):
            await jobs.count_jobs("queued")
    finally:
        await served.close()


async def test_a_database_without_vector_is_refused_before_any_migration(
    storage: PostgresStorage, database_url: str
) -> None:
    name = f"bare_{uuid4().hex[:8]}"
    owner = await asyncpg.connect(database_url)
    try:
        await owner.execute(f"CREATE DATABASE {name}")
    finally:
        await owner.close()
    parts = urlsplit(database_url)
    bare = urlunsplit((parts.scheme, parts.netloc, f"/{name}", parts.query, ""))
    with pytest.raises(ExtensionMissingError, match="provisioner creates it"):
        await migrate(bare, migrations_dir())
    check = await asyncpg.connect(bare)
    try:
        assert await check.fetchval("SELECT to_regclass('schema_migrations')") is None
    finally:
        await check.close()
    assert "db/provision/extensions.sql" in VECTOR_MISSING


async def test_the_database_under_test_is_the_managed_tiers_pgvector(
    storage: PostgresStorage, database_url: str
) -> None:
    connection = await asyncpg.connect(database_url)
    try:
        version = await connection.fetchval(sql("vector_version"))
    finally:
        await connection.close()
    assert version == rules.CI_PGVECTOR
