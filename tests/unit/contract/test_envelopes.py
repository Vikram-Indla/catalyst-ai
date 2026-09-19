"""Envelopes: classification metadata, forbidden extras, usage bounds."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from catalyst_ai.contract.envelopes import (
    DATA_CLASS_KEY,
    RequestEnvelope,
    ResponseEnvelope,
    Usage,
    classified,
)


def test_classified_carries_the_key() -> None:
    assert classified("PUBLIC", "d") == {DATA_CLASS_KEY: "PUBLIC", "description": "d"}


def test_request_envelope_forbids_extras_and_checks_version() -> None:
    RequestEnvelope(organization_id=uuid4(), capability_version="1.0.0")
    with pytest.raises(ValidationError):
        RequestEnvelope(organization_id=uuid4(), capability_version="1.0")
    with pytest.raises(ValidationError):
        RequestEnvelope.model_validate(
            {"organization_id": str(uuid4()), "capability_version": "1.0.0", "x": 1}
        )


def test_request_schema_declares_data_classes() -> None:
    properties = RequestEnvelope.model_json_schema()["properties"]
    assert all(DATA_CLASS_KEY in spec for spec in properties.values())


def test_usage_rejects_negative_numbers() -> None:
    usage = Usage(input_tokens=1, output_tokens=2, cost_micros=3, latency_ms=4, cache_hit=False)
    assert usage.cost_micros == 3
    with pytest.raises(ValidationError):
        Usage(input_tokens=-1, output_tokens=2, cost_micros=3, latency_ms=4, cache_hit=False)


def test_response_envelope_shape() -> None:
    usage = Usage(input_tokens=0, output_tokens=0, cost_micros=0, latency_ms=0, cache_hit=True)
    envelope = ResponseEnvelope(
        capability_version="1.0.0",
        prompt_version="1",
        model="text-default@x",
        eval_set_version="1",
        usage=usage,
        request_id="r",
    )
    assert envelope.usage.cache_hit is True
