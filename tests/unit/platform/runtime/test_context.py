"""The runtime context is frozen and carries its seams and the credential probe."""

import dataclasses

import pytest

from catalyst_ai.platform.runtime import RuntimeContext


def test_context_is_frozen_with_its_seams() -> None:
    names = {f.name for f in dataclasses.fields(RuntimeContext)}
    assert names == {
        "settings",
        "provider",
        "cache",
        "budgets",
        "clock",
        "storage",
        "jobs",
        "metrics",
        "credentials_ready",
    }
    with pytest.raises(dataclasses.FrozenInstanceError):
        RuntimeContext.__setattr__(RuntimeContext.__new__(RuntimeContext), "clock", None)
