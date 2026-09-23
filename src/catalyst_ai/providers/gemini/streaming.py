"""Gemini's streamed generation: server-sent `data:` lines become the port's frames."""

import json
from collections.abc import AsyncIterator, Callable
from typing import Any

from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.providers.gemini import errors
from catalyst_ai.providers.gemini.models import ModelSpec, billed_output_tokens
from catalyst_ai.providers.port import StreamFrame

STREAM_METHOD = "streamGenerateContent"
STREAM_QUERY = "alt=sse"
DATA_PREFIX = "data:"
SHAPE_EMPTY_STREAM = "the stream carried no chunk"


def chunk_text(payload: dict[str, Any]) -> str:
    """Return the text a chunk carries, if any."""
    candidates = payload.get("candidates") or []
    if not candidates:
        return ""
    parts = (candidates[0].get("content") or {}).get("parts") or []
    return "".join(str(part.get("text", "")) for part in parts)


def chunk_usage(payload: dict[str, Any], spec: ModelSpec, latency_ms: int) -> Usage | None:
    """Return the usage a chunk states — the totals so far — or None when it states none."""
    meta = payload.get("usageMetadata")
    if not meta:
        return None
    input_tokens = int(meta.get("promptTokenCount", 0))
    output_tokens = billed_output_tokens(meta)
    return Usage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_micros=spec.cost_micros(input_tokens, output_tokens),
        latency_ms=latency_ms,
        cache_hit=False,
    )


def _blocked(payload: dict[str, Any], request_id: str) -> None:
    candidates = payload.get("candidates") or []
    reason = (candidates[0].get("finishReason") if candidates else None) or (
        payload.get("promptFeedback") or {}
    ).get("blockReason")
    error = errors.from_finish_reason(reason, request_id)
    if error is not None:
        raise error


def payloads_of(lines: AsyncIterator[str]) -> AsyncIterator[dict[str, Any]]:
    """Yield each `data:` line's JSON object; other lines are the protocol's and are skipped."""

    async def _payloads() -> AsyncIterator[dict[str, Any]]:
        async for line in lines:
            if not line.startswith(DATA_PREFIX):
                continue
            body = line[len(DATA_PREFIX) :].strip()
            if body:
                loaded: dict[str, Any] = json.loads(body)
                yield loaded

    return _payloads()


async def frames_of(
    lines: AsyncIterator[str], spec: ModelSpec, request_id: str, latency_of: Callable[[], float]
) -> AsyncIterator[StreamFrame]:
    """Turn the response lines into `delta` frames, one `usage` frame and one `done` frame.

    `latency_of` is a callable returning the milliseconds elapsed so far; a blocked finish
    reason raises the port's error, which the caller turns into the terminal `error` frame.
    """
    usage: Usage | None = None
    model_id = spec.model_id
    seen = False
    async for payload in payloads_of(lines):
        seen = True
        _blocked(payload, request_id)
        text = chunk_text(payload)
        if text:
            yield StreamFrame(kind="delta", text=text)
        usage = chunk_usage(payload, spec, int(latency_of())) or usage
        model_id = str(payload.get("modelVersion") or model_id)
    if not seen:
        raise errors.from_shape(SHAPE_EMPTY_STREAM, request_id)
    if usage is None:
        usage = Usage(
            input_tokens=0,
            output_tokens=0,
            cost_micros=0,
            latency_ms=int(latency_of()),
            cache_hit=False,
        )
    yield StreamFrame(kind="usage", usage=usage, model_id=model_id)
    yield StreamFrame(kind="done", model_id=model_id)
