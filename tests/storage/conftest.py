"""A real PostgreSQL with pgvector for the storage tests: the one named, else a container."""

import os
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from pytest_socket import enable_socket
from testcontainers.postgres import PostgresContainer

from catalyst_ai.platform.storage import PostgresStorage, migrate
from tests.conftest import REPO_ROOT
from tests.unit.capabilities.improve_story.conftest import FrozenClock
from tools.evalkit import DATABASE_IMAGE, DATABASE_VARIABLE, container_dsn

MIGRATIONS = REPO_ROOT / "db" / "migrations"
COMMAND_TIMEOUT_S = 10.0
MIGRATED: set[str] = set()


@pytest.fixture(scope="session")
def database_url() -> Iterator[str]:
    enable_socket()
    provided = os.environ.get(DATABASE_VARIABLE)
    if provided:
        yield provided
        return
    with PostgresContainer(DATABASE_IMAGE, driver=None) as container:
        yield container_dsn(container)


@pytest.fixture
async def storage(database_url: str) -> AsyncIterator[PostgresStorage]:
    if database_url not in MIGRATED:
        await migrate(database_url, MIGRATIONS)
        MIGRATED.add(database_url)
    store = PostgresStorage(database_url, FrozenClock(), 4, COMMAND_TIMEOUT_S)
    await store.connect()
    yield store
    await store.close()


def migrations_dir() -> Path:
    return MIGRATIONS
