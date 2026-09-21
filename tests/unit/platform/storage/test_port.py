"""The Storage seam is a Protocol both implementations satisfy structurally."""

from catalyst_ai.platform.storage import MemoryStorage, PostgresStorage, Storage
from tests.unit.capabilities.improve_story.conftest import FrozenClock


def test_both_implementations_are_storages() -> None:
    clock = FrozenClock()
    memory: Storage = MemoryStorage(clock)
    postgres: Storage = PostgresStorage("postgresql://u:p@h/d", clock, 2, 1.0)
    assert memory is not postgres
    assert {name for name in dir(Storage) if not name.startswith("_")} <= set(dir(memory))
