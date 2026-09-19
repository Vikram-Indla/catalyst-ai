"""Health responses accept only their literals."""

import pytest
from pydantic import ValidationError

from catalyst_ai.contract.health import LiveResponse, ReadyResponse


def test_live_literal() -> None:
    assert LiveResponse(status="live").status == "live"
    with pytest.raises(ValidationError):
        LiveResponse.model_validate({"status": "dead"})


def test_ready_carries_checks() -> None:
    ready = ReadyResponse(status="not_ready", checks={"settings": False})
    assert ready.checks == {"settings": False}
