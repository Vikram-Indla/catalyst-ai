"""The adapter over a scripted transport: body shape, retries, breaker, cost, every error mapping."""

from datetime import UTC, datetime, timedelta
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
from catalyst_ai.providers.gemini.adapter import BREAKER_FAILURES, build_body
from catalyst_ai.providers.gemini.models import FLASH
from catalyst_ai.providers.port import EmbedRequest, GenerateRequest, ModelAlias, Segment

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
        service_tokens=[SecretStr("t")],
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
    body = build_body(_request())
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


async def test_stream_and_embed_are_not_implemented_yet() -> None:
    adapter, _, _ = _adapter([Fault()])
    with pytest.raises(NotImplementedError):
        adapter.stream(_request())
    embed = EmbedRequest(
        organization_id=uuid4(),
        capability="c",
        alias=ModelAlias.EMBED_DEFAULT,
        texts=["x"],
        timeout_ms=1,
    )
    with pytest.raises(NotImplementedError):
        await adapter.embed(embed)


def test_count_tokens_estimates_by_characters() -> None:
    adapter, _, _ = _adapter([Fault()])
    assert adapter.count_tokens(ModelAlias.TEXT_DEFAULT, "x" * 40) == 10
    assert adapter.count_tokens(ModelAlias.TEXT_DEFAULT, "") == 1
