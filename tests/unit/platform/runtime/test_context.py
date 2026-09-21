"""The runtime context is frozen and carries the six seams."""

import dataclasses

import pytest

from catalyst_ai.platform.runtime import RuntimeContext


def test_context_is_frozen_with_six_fields() -> None:
    names = {f.name for f in dataclasses.fields(RuntimeContext)}
    assert names == {"settings", "provider", "cache", "budgets", "clock", "storage"}
    with pytest.raises(dataclasses.FrozenInstanceError):
        RuntimeContext.__setattr__(RuntimeContext.__new__(RuntimeContext), "clock", None)
