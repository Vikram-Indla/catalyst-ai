"""The migration runner: pending files in name order, applied ones skipped."""

from pathlib import Path

import pytest

from catalyst_ai.platform.storage import StorageUnavailableError, migrate
from catalyst_ai.platform.storage.migrate import pending


def test_pending_orders_by_name_and_skips_applied(tmp_path: Path) -> None:
    (tmp_path / "20260102000000_b.sql").write_text("-- migration: b", encoding="utf-8")
    (tmp_path / "20260101000000_a.sql").write_text("-- migration: a", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    names = [name for name, _ in pending(tmp_path, {"20260101000000_a.sql"})]
    assert names == ["20260102000000_b.sql"]
    assert pending(tmp_path, set())[0][0] == "20260101000000_a.sql"


async def test_migrate_reports_an_unreachable_database(tmp_path: Path) -> None:
    with pytest.raises(StorageUnavailableError):
        await migrate("postgresql://u:p@127.0.0.1:1/d", tmp_path)
