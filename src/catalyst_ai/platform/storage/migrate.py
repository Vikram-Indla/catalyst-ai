"""The migration runner: forward-only SQL files, each applied once, in name order."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import asyncpg

from catalyst_ai.platform.storage.postgres import StorageUnavailableError, sql

CONNECT_TIMEOUT_S = 10.0
MIGRATION_SUFFIX = ".sql"


def pending(directory: Path, applied: set[str]) -> list[tuple[str, str]]:
    """Return the migration files not yet applied as (name, text), in name order."""
    files = sorted(
        path
        for path in directory.glob(f"*{MIGRATION_SUFFIX}")
        if path.is_file() and path.name not in applied
    )
    return [(path.name, path.read_text(encoding="utf-8")) for path in files]


async def _apply(connection: asyncpg.Connection[Any], name: str, text: str) -> None:
    async with connection.transaction():
        await connection.execute(text)
        await connection.execute(sql("migrations_record"), name)


async def migrate(dsn: str, directory: Path) -> list[str]:
    """Apply every pending migration as the owner; return the names applied."""
    try:
        connection = await asyncpg.connect(dsn, timeout=CONNECT_TIMEOUT_S)
    except (OSError, asyncpg.PostgresError) as error:
        raise StorageUnavailableError(str(type(error).__name__)) from error
    try:
        await connection.execute(sql("migrations_table"))
        applied = {str(row["name"]) for row in await connection.fetch(sql("migrations_applied"))}
        names = []
        for name, text in pending(directory, applied):
            await _apply(connection, name, text)
            names.append(name)
    finally:
        await connection.close()
    return names
