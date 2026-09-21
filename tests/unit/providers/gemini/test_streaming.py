"""The stream parser: data lines to frames, usage from the last chunk, a blocked reason raised."""

import json
from collections.abc import AsyncIterator

import pytest

from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from catalyst_ai.providers.gemini.models import FLASH
from catalyst_ai.providers.gemini.streaming import chunk_text, chunk_usage, frames_of, payloads_of


async def _lines(*lines: str) -> AsyncIterator[str]:
    for line in lines:
        yield line


def _chunk(text: str, finish: str | None = None, **extra: object) -> str:
    candidate: dict[str, object] = {"content": {"parts": [{"text": text}]}}
    if finish is not None:
        candidate["finishReason"] = finish
    return "data: " + json.dumps({"candidates": [candidate], **extra})


async def test_payloads_skip_comments_and_blank_lines() -> None:
    lines = _lines(": comment", "", _chunk("a"), "event: x", _chunk("b"))
    assert [chunk_text(p) for p in [x async for x in payloads_of(lines)]] == ["a", "b"]
    assert chunk_text({}) == ""
    assert chunk_usage({}, FLASH, 5) is None


async def test_frames_carry_deltas_then_the_last_usage_and_the_model() -> None:
    usage = {"promptTokenCount": 10, "candidatesTokenCount": 4}
    lines = _lines(_chunk("x"), _chunk("y", usageMetadata=usage, modelVersion="m-2"))
    frames = [f async for f in frames_of(lines, FLASH, "rid", lambda: 7.0)]
    assert [f.kind for f in frames] == ["delta", "delta", "usage", "done"]
    assert frames[2].usage is not None
    assert frames[2].usage.latency_ms == 7
    assert frames[2].usage.cost_micros == FLASH.cost_micros(10, 4)
    assert frames[3].model_id == "m-2"
    bare = [f async for f in frames_of(_lines(_chunk("z")), FLASH, "rid", lambda: 3.0)]
    assert bare[1].usage is not None
    assert bare[1].usage.cost_micros == 0


async def test_a_blocked_chunk_raises_the_catalog_error() -> None:
    blocked = _lines(_chunk("", finish="SAFETY"))
    with pytest.raises(Error) as caught:
        _ = [f async for f in frames_of(blocked, FLASH, "rid", lambda: 0.0)]
    assert caught.value.code is ErrorCode.PROVIDER_REJECTED
