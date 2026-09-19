"""The provider-call row has no content field and logs as one structured line."""

import logging
from uuid import uuid4

import pytest

from catalyst_ai.platform.logging import CONTENT_KEYS
from catalyst_ai.platform.observability import ProviderCallRow, log_provider_call


def _row() -> ProviderCallRow:
    return ProviderCallRow(
        organization_id=uuid4(),
        capability="c",
        capability_version="1.0.0",
        prompt_version="1",
        model_alias="text-default",
        model_id="m",
        input_tokens=1,
        output_tokens=2,
        cost_micros=3,
        latency_ms=4,
        cache_hit=False,
        outcome="ok",
        request_id="r",
    )


def test_row_has_no_content_field() -> None:
    assert not set(ProviderCallRow.model_fields) & CONTENT_KEYS


def test_log_provider_call_emits_the_row(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.INFO, logger="catalyst_ai.provider_calls"):
        log_provider_call(_row())
    record = caplog.records[-1]
    assert record.getMessage() == "provider call"
    assert record.__dict__["capability"] == "c"
    assert record.__dict__["cost_micros"] == 3
