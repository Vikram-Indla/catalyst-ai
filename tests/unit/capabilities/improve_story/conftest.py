"""Doubles for the pipeline: a scripted provider behind the port and a runtime around it."""

from collections.abc import AsyncIterator
from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import SecretStr

from catalyst_ai.config import CapabilitySettings, Environment, Settings
from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.contract.improve_story import ImproveStoryMode, ImproveStoryRequest
from catalyst_ai.platform.budgets import TenantBudgets
from catalyst_ai.platform.cache import MemoryCache
from catalyst_ai.platform.runtime import RuntimeContext
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


class FrozenClock:
    def __init__(self) -> None:
        self.at = datetime(2026, 9, 18, 12, 0, tzinfo=UTC)

    def now(self) -> datetime:
        return self.at


class ScriptedProvider:
    """Answers with the next scripted text; the last repeats; every call is counted."""

    def __init__(self, texts: list[str]) -> None:
        self.texts = list(texts)
        self.calls: list[GenerateRequest] = []

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        self.calls.append(request)
        text = self.texts.pop(0) if len(self.texts) > 1 else self.texts[0]
        usage = Usage(
            input_tokens=100, output_tokens=50, cost_micros=155, latency_ms=20, cache_hit=False
        )
        return GenerateResult(text=text, model_id="double", usage=usage)

    def stream(self, request: GenerateRequest) -> AsyncIterator[StreamFrame]:
        raise NotImplementedError

    async def embed(self, request: EmbedRequest) -> EmbedResult:
        raise NotImplementedError

    def count_tokens(self, alias: ModelAlias, text: str) -> int:
        return max(1, len(text) // 4)


def make_settings(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "environment": Environment.DEVELOPMENT,
        "service_tokens": [SecretStr("t")],
        "database_url": SecretStr("postgresql://u:p@h/d"),
        "capability_improve_story": CapabilitySettings(),
    }
    values.update(overrides)
    return Settings.model_validate(values)


def make_runtime(provider: ScriptedProvider, settings: Settings | None = None) -> RuntimeContext:
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
