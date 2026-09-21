"""Doubles for the pipeline: a scripted provider behind the port and a runtime around it."""

import hashlib
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import SecretStr

from catalyst_ai.config import CapabilitySettings, Environment, Settings
from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.improve_story import ImproveStoryMode, ImproveStoryRequest
from catalyst_ai.platform.budgets import TenantBudgets
from catalyst_ai.platform.cache import MemoryCache
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.platform.storage import MemoryStorage, Storage
from catalyst_ai.providers.port import (
    EmbedRequest,
    EmbedResult,
    GenerateRequest,
    GenerateResult,
    ModelAlias,
    StreamFrame,
)

ORG = UUID("11111111-1111-7111-8111-111111111111")
OTHER_ORG = UUID("22222222-2222-7222-8222-222222222222")
GOOD_TEXT = '{"description": "Improved text.", "acceptance_criteria": null, "rationale": "Tightened the phrasing.", "changed": true}'
DOUBLE_MODEL = "double"
EMBED_DIMENSIONS = 64
TOKEN = re.compile(r"[^\W_]+")


def hashed_vector(text: str, dimensions: int = EMBED_DIMENSIONS) -> list[float]:
    """A bag-of-words vector: tokens hashed into buckets; similar texts land close together."""
    values = [0.0] * dimensions
    for token in TOKEN.findall(text.lower()):
        digest = hashlib.sha256(token[:4].encode()).digest()
        values[digest[0] % dimensions] += 1.0 if digest[1] % 2 else -1.0
    norm = sum(v * v for v in values) ** 0.5
    return [v / norm for v in values] if norm else values


class FrozenClock:
    def __init__(self) -> None:
        self.at = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.at


STREAM_PIECE = 7
STREAM_FAULT = "<<stream fault>>"


class ScriptedProvider:
    """Answers with the next scripted text; the last repeats; every call is counted."""

    def __init__(self, texts: list[str]) -> None:
        self.texts = list(texts)
        self.calls: list[GenerateRequest] = []
        self.embed_calls: list[EmbedRequest] = []

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        self.calls.append(request)
        text = self.texts.pop(0) if len(self.texts) > 1 else self.texts[0]
        usage = Usage(
            input_tokens=100, output_tokens=50, cost_micros=155, latency_ms=20, cache_hit=False
        )
        return GenerateResult(text=text, model_id="double", usage=usage)

    async def stream(self, request: GenerateRequest) -> AsyncIterator[StreamFrame]:
        """Stream the next scripted text in pieces of `STREAM_PIECE` characters, then finish."""
        self.calls.append(request)
        text = self.texts.pop(0) if len(self.texts) > 1 else self.texts[0]
        if text == STREAM_FAULT:
            raise Error(ErrorCode.PROVIDER_UNAVAILABLE, "the double broke the stream")
        for start in range(0, len(text), STREAM_PIECE):
            yield StreamFrame(kind="delta", text=text[start : start + STREAM_PIECE])
        usage = Usage(
            input_tokens=100, output_tokens=50, cost_micros=155, latency_ms=20, cache_hit=False
        )
        yield StreamFrame(kind="usage", usage=usage, model_id="double")
        yield StreamFrame(kind="done", model_id="double")

    async def embed(self, request: EmbedRequest) -> EmbedResult:
        self.embed_calls.append(request)
        tokens = sum(max(1, len(t) // 4) for t in request.texts)
        usage = Usage(
            input_tokens=tokens, output_tokens=0, cost_micros=tokens, latency_ms=3, cache_hit=False
        )
        return EmbedResult(
            vectors=[hashed_vector(t) for t in request.texts], model_id=DOUBLE_MODEL, usage=usage
        )

    def count_tokens(self, alias: ModelAlias, text: str) -> int:
        return max(1, len(text) // 4)

    def model_id(self, alias: ModelAlias) -> str:
        return DOUBLE_MODEL


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": Environment.DEVELOPMENT,
        "service_tokens": [SecretStr("t")],
        "database_url": SecretStr("postgresql://u:p@h/d"),
        "capability_improve_story": CapabilitySettings(),
    }
    values.update(overrides)
    return Settings.model_validate(values)


def make_runtime(
    provider: ScriptedProvider, settings: Settings | None = None, storage: Storage | None = None
) -> RuntimeContext:
    resolved = settings or make_settings()
    clock = FrozenClock()
    return RuntimeContext(
        settings=resolved,
        provider=provider,
        cache=MemoryCache(clock),
        budgets=TenantBudgets(
            clock, resolved.tenant_budget_default_micros_per_day, resolved.tenant_concurrency_max
        ),
        clock=clock,
        storage=storage or MemoryStorage(clock),
    )


def make_request(**overrides: object) -> ImproveStoryRequest:
    values: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "mode": ImproveStoryMode.CLARIFY,
        "item_type": "Story",
        "title": "Export board",
        "description": "as a PM i want export the board to csv, see PROJ-42",
    }
    values.update(overrides)
    return ImproveStoryRequest.model_validate(values)


@pytest.fixture
def provider() -> ScriptedProvider:
    return ScriptedProvider([GOOD_TEXT])


@pytest.fixture
def runtime(provider: ScriptedProvider) -> RuntimeContext:
    return make_runtime(provider)
