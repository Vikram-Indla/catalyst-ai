"""The frames: one discriminator, the terminal pair, the envelope every stream may end with."""

import pytest
from pydantic import TypeAdapter, ValidationError

from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.contract.errors import ErrorBody, ErrorCode, ErrorEnvelope
from catalyst_ai.contract.streaming import (
    DeltaFrame,
    ErrorFrame,
    Frame,
    StreamEnvelope,
    UsageFrame,
)


def test_frames_discriminate_on_kind() -> None:
    adapter: TypeAdapter[object] = TypeAdapter(Frame)
    delta = adapter.validate_python({"kind": "delta", "text": "hi"})
    assert isinstance(delta, DeltaFrame)
    usage = Usage(input_tokens=1, output_tokens=1, cost_micros=1, latency_ms=1, cache_hit=False)
    assert isinstance(adapter.validate_python({"kind": "usage", "usage": usage}), UsageFrame)
    body = ErrorBody(code=ErrorCode.BUDGET_EXCEEDED, message="spent", details=[])
    error = ErrorFrame(error=ErrorEnvelope(error=body, request_id="r"))
    assert StreamEnvelope(frame=error).frame.kind == "error"
    with pytest.raises(ValidationError):
        adapter.validate_python({"kind": "start"})
    with pytest.raises(ValidationError):
        DeltaFrame(text="x" * 4_001)
