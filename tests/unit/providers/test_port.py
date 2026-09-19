"""The port's models validate their bounds."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from catalyst_ai.providers.port import GenerateRequest, ModelAlias, Segment, StreamFrame


def _request(**overrides: object) -> GenerateRequest:
    values: dict[str, object] = {
        "organization_id": uuid4(),
        "request_id": "rid",
        "capability": "x",
        "alias": ModelAlias.TEXT_DEFAULT,
        "segments": [Segment(role="user", name="title", text="t")],
        "temperature": 0.2,
        "max_output_tokens": 10,
        "timeout_ms": 1000,
    }
    values.update(overrides)
    return GenerateRequest.model_validate(values)


def test_request_validates() -> None:
    assert _request().alias is ModelAlias.TEXT_DEFAULT


@pytest.mark.parametrize(
    "overrides",
    [{"segments": []}, {"temperature": 3.0}, {"max_output_tokens": 0}, {"timeout_ms": 0}],
    ids=["no segments", "temperature", "tokens", "timeout"],
)
def test_request_bounds(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _request(**overrides)


def test_stream_frame_defaults() -> None:
    frame = StreamFrame(kind="delta", text="a")
    assert frame.usage is None
    assert frame.model_id is None
