"""The adapter over a scripted transport: body shape, retries, breaker, cost, every error mapping."""

import json
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import httpx
import pytest
from pydantic import SecretStr

from catalyst_ai.config import Environment, Settings
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.resilience import RetryPolicy
from catalyst_ai.providers.faults import Fault, FaultTransport
from catalyst_ai.providers.gemini import GeminiProvider
from catalyst_ai.providers.gemini.adapter import (
    BREAKER_FAILURES,
    EMBED_DIMENSIONS,
    build_body,
    build_embed_body,
    normalise,
)
from catalyst_ai.providers.gemini.models import EMBEDDING, FLASH
from catalyst_ai.providers.port import (
    EmbedRequest,
    GenerateRequest,
    ModelAlias,
    Segment,
    StreamFrame,
)
from tools import origin

OK_BODY: dict[str, object] = {
    "candidates": [{"content": {"parts": [{"text": '{"a": 1}'}]}, "finishReason": "STOP"}],
    "usageMetadata": {"promptTokenCount": 1000, "candidatesTokenCount": 1000},
    "modelVersion": "flash-2026",
}


class FrozenClock:
    def __init__(self) -> None:
        self.at = datetime(2026, 9, 18, tzinfo=UTC)

    def now(self) -> datetime:
        return self.at


def _settings() -> Settings:
    return Settings(
        environment=Environment.DEVELOPMENT,
        auth_public_keys=origin.PUBLIC_KEYS,
        database_url=SecretStr("postgresql://u:p@h/d"),
        provider_gemini_api_key=SecretStr("key"),
    )


def _request() -> GenerateRequest:
    return GenerateRequest(
        organization_id=uuid4(),
        request_id="rid",
        capability="c",
        alias=ModelAlias.TEXT_DEFAULT,
        segments=[
            Segment(role="system", name="system", text="sys"),
            Segment(role="developer", name="developer", text="dev"),
            Segment(role="user", name="title", text="usr"),
        ],
        output_schema={
            "type": "object",
            "title": "T",
            "properties": {"a": {"type": "integer", "title": "A"}},
        },
        temperature=0.2,
        max_output_tokens=100,
        timeout_ms=1000,
    )


FAST = RetryPolicy(attempts=3, base_ms=0, max_ms=0, seed=1)
ONCE = RetryPolicy(attempts=1, base_ms=0, max_ms=0, seed=1)


def _adapter(
    script: list[Fault], policy: RetryPolicy = FAST
) -> tuple[GeminiProvider, FaultTransport, FrozenClock]:
    transport = FaultTransport(script)
    clock = FrozenClock()
    client = httpx.AsyncClient(transport=transport, timeout=1.0)
    return GeminiProvider(_settings(), client, clock, policy), transport, clock


def test_body_shape_drops_schema_titles() -> None:
    body = build_body(_request(), FLASH)
    assert body["systemInstruction"] == {"parts": [{"text": "sys"}]}
    assert body["contents"][0]["parts"][0]["text"] == "dev\n\nusr"
    schema = body["generationConfig"]["responseSchema"]
    assert "title" not in schema
    assert "title" not in schema["properties"]["a"]
    assert body["generationConfig"]["responseMimeType"] == "application/json"


async def test_generate_parses_text_usage_cost_and_model() -> None:
    adapter, _, _ = _adapter([Fault(body=OK_BODY)])
    result = await adapter.generate(_request())
    assert result.text == '{"a": 1}'
    assert result.model_id == "flash-2026"
    assert result.usage.cost_micros == FLASH.cost_micros(1000, 1000)
    assert result.usage.cache_hit is False


async def test_retries_a_transient_failure_then_succeeds() -> None:
    adapter, transport, _ = _adapter([Fault(status=503), Fault(body=OK_BODY)])
    await adapter.generate(_request())
    assert transport.calls == 2


@pytest.mark.parametrize(
    ("fault", "code"),
    [
        (Fault(status=429), ErrorCode.PROVIDER_QUOTA),
        (Fault(status=400), ErrorCode.PROVIDER_REJECTED),
        (Fault(raises=httpx.ReadTimeout), ErrorCode.PROVIDER_TIMEOUT),
        (Fault(raises=httpx.ConnectError), ErrorCode.PROVIDER_UNAVAILABLE),
        (Fault(body={"candidates": [{"finishReason": "SAFETY"}]}), ErrorCode.PROVIDER_REJECTED),
        (Fault(body={"promptFeedback": {"blockReason": "SAFETY"}}), ErrorCode.PROVIDER_REJECTED),
    ],
    ids=["quota", "rejected", "timeout", "connect", "finish safety", "prompt blocked"],
)
async def test_failures_map_to_the_catalog(fault: Fault, code: ErrorCode) -> None:
    adapter, _, _ = _adapter([fault], ONCE)
    with pytest.raises(Error) as caught:
        await adapter.generate(_request())
    assert caught.value.code is code


async def test_breaker_opens_after_failures_and_half_opens_later() -> None:
    adapter, transport, clock = _adapter([Fault(status=503)], ONCE)
    for _ in range(BREAKER_FAILURES):
        with pytest.raises(Error):
            await adapter.generate(_request())
    calls_before = transport.calls
    with pytest.raises(Error) as caught:
        await adapter.generate(_request())
    assert caught.value.code is ErrorCode.PROVIDER_UNAVAILABLE
    assert transport.calls == calls_before
    clock.at += timedelta(seconds=31)
    with pytest.raises(Error):
        await adapter.generate(_request())
    assert transport.calls == calls_before + 1


def _embed_request(texts: list[str]) -> EmbedRequest:
    return EmbedRequest(
        organization_id=uuid4(),
        capability="c",
        alias=ModelAlias.EMBED_DEFAULT,
        texts=texts,
        purpose="query",
        timeout_ms=1000,
    )


def _embed_body(count: int) -> dict[str, object]:
    return {"embeddings": [{"values": [1.0] + [0.0] * (EMBED_DIMENSIONS - 1)}] * count}


def _sse(*texts: str, finish: str = "STOP") -> str:
    chunks: list[dict[str, Any]] = [
        {"candidates": [{"content": {"parts": [{"text": t}]}}]} for t in texts
    ]
    chunks[-1]["candidates"][0]["finishReason"] = finish
    chunks[-1]["usageMetadata"] = {"promptTokenCount": 30, "candidatesTokenCount": 12}
    chunks[-1]["modelVersion"] = "double-stream-model"
    return "".join(f"data: {json.dumps(chunk)}" + chr(10) * 2 for chunk in chunks)


async def _frames(adapter: GeminiProvider) -> list[StreamFrame]:
    return [frame async for frame in adapter.stream(_request())]


async def test_stream_yields_deltas_then_usage_then_done() -> None:
    adapter, transport, _ = _adapter([Fault(raw=_sse("Hel", "lo ", "there."))])
    frames = await _frames(adapter)
    assert [f.kind for f in frames] == ["delta", "delta", "delta", "usage", "done"]
    assert "".join(f.text for f in frames if f.kind == "delta") == "Hello there."
    usage = frames[3].usage
    assert usage is not None
    assert (usage.input_tokens, usage.output_tokens) == (30, 12)
    assert usage.cost_micros == FLASH.cost_micros(30, 12)
    assert frames[4].model_id == "double-stream-model"
    assert transport.calls == 1


@pytest.mark.parametrize(
    ("fault", "code"),
    [
        (Fault(status=503), ErrorCode.PROVIDER_UNAVAILABLE),
        (Fault(raises=httpx.ReadTimeout), ErrorCode.PROVIDER_TIMEOUT),
        (Fault(raw=_sse("x", finish="SAFETY")), ErrorCode.PROVIDER_REJECTED),
        (Fault(raw=": keep-alive" + chr(10) * 2), ErrorCode.PROVIDER_UNAVAILABLE),
    ],
    ids=["unavailable", "timeout", "blocked", "empty"],
)
async def test_stream_failures_map_to_the_catalog_and_never_retry(
    fault: Fault, code: ErrorCode
) -> None:
    adapter, transport, _ = _adapter([fault])
    with pytest.raises(Error) as caught:
        await _frames(adapter)
    assert caught.value.code is code
    assert transport.calls == 1


def test_embed_body_carries_the_task_type_and_the_dimensions() -> None:
    body = build_embed_body(_embed_request(["a", "b"]), EMBEDDING.model_id)
    requests = body["requests"]
    assert len(requests) == 2
    assert requests[0]["taskType"] == "RETRIEVAL_QUERY"
    assert requests[0]["outputDimensionality"] == EMBED_DIMENSIONS
    assert requests[1]["content"] == {"parts": [{"text": "b"}]}


async def test_embed_returns_unit_vectors_with_estimated_cost() -> None:
    adapter, transport, _ = _adapter([Fault(body=_embed_body(2))])
    result = await adapter.embed(_embed_request(["a" * 400, "b" * 400]))
    assert len(result.vectors) == 2
    assert all(len(vector) == EMBED_DIMENSIONS for vector in result.vectors)
    assert abs(sum(v * v for v in result.vectors[0]) - 1.0) < 1e-9
    assert result.usage.input_tokens == 200
    assert result.usage.cost_micros == EMBEDDING.cost_micros(200, 0)
    assert result.model_id == EMBEDDING.model_id
    assert transport.calls == 1


def test_normalise_scales_to_unit_length_and_leaves_a_null_vector() -> None:
    assert normalise([3.0, 4.0]) == [0.6, 0.8]
    assert normalise([0.0, 0.0]) == [0.0, 0.0]


@pytest.mark.parametrize(
    "body",
    [{"embeddings": []}, {"embeddings": [{"values": [1.0, 2.0]}]}, {"other": 1}],
    ids=["empty", "wrong size", "no key"],
)
async def test_embed_refuses_an_unreadable_body(body: dict[str, object]) -> None:
    adapter, _, _ = _adapter([Fault(body=body)], ONCE)
    with pytest.raises(Error) as caught:
        await adapter.embed(_embed_request(["a"]))
    assert caught.value.code is ErrorCode.PROVIDER_UNAVAILABLE


async def test_embed_failures_map_to_the_catalog() -> None:
    adapter, _, _ = _adapter([Fault(status=429)], ONCE)
    with pytest.raises(Error) as caught:
        await adapter.embed(_embed_request(["a"]))
    assert caught.value.code is ErrorCode.PROVIDER_QUOTA


def test_model_id_resolves_the_alias_through_the_register() -> None:
    adapter, _, _ = _adapter([Fault()])
    assert adapter.model_id(ModelAlias.EMBED_DEFAULT) == EMBEDDING.model_id


THINKING_BODY: dict[str, object] = {
    **OK_BODY,
    "usageMetadata": {"promptTokenCount": 7, "candidatesTokenCount": 1, "thoughtsTokenCount": 57},
}


async def test_thinking_tokens_are_billed_as_output() -> None:
    adapter, _, _ = _adapter([Fault(body=THINKING_BODY)])
    result = await adapter.generate(_request())
    assert result.usage.output_tokens == 58
    assert result.usage.cost_micros == FLASH.cost_micros(7, 58)


def test_a_row_with_a_thinking_level_sends_it_and_a_row_without_sends_none() -> None:
    thinking = replace(FLASH, thinking_level="minimal")
    config = build_body(_request(), thinking)["generationConfig"]
    assert config["thinkingConfig"] == {"thinkingLevel": "minimal"}
    assert "thinkingConfig" not in build_body(_request(), FLASH)["generationConfig"]
