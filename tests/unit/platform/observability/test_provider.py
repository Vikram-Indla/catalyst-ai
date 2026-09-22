"""The metered port: every call counted by capability, model and outcome, with its usage."""

import pytest

from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.observability import MeteredProvider, Metrics
from catalyst_ai.platform.observability.metrics import (
    PROVIDER_CALLS,
    PROVIDER_COST_MICROS,
    PROVIDER_SECONDS,
    PROVIDER_TOKENS,
)
from catalyst_ai.providers.port import (
    EmbedRequest,
    EmbedResult,
    GenerateRequest,
    GenerateResult,
    ModelAlias,
    Segment,
)
from tests.unit.capabilities.improve_story.conftest import FrozenClock, ScriptedProvider
from tools import origin

CAP = "improve-story"
MODEL = "double"
GOOD = '{"description": "Better.", "acceptance_criteria": null, "rationale": "Tighter.", "changed": true}'


def _request() -> GenerateRequest:
    return GenerateRequest(
        organization_id=origin.ORG,
        request_id="r1",
        capability=CAP,
        alias=ModelAlias.TEXT_DEFAULT,
        segments=[Segment(role="system", name="instructions", text="You improve stories.")],
        temperature=0.2,
        max_output_tokens=512,
        timeout_ms=8000,
    )


def _metered(provider: ScriptedProvider) -> tuple[MeteredProvider, Metrics]:
    metrics = Metrics()
    return MeteredProvider(provider, metrics, FrozenClock()), metrics


async def test_a_generation_is_counted_with_its_tokens_cost_and_duration() -> None:
    metered, metrics = _metered(ScriptedProvider([GOOD]))
    result = await metered.generate(_request())
    labels = {"capability": CAP, "model": MODEL}
    assert result.text == GOOD
    assert metrics.value(PROVIDER_CALLS, {**labels, "outcome": "ok"}) == 1
    assert metrics.value(PROVIDER_TOKENS, {**labels, "direction": "input"}) > 0
    assert metrics.value(PROVIDER_TOKENS, {**labels, "direction": "output"}) > 0
    assert metrics.value(PROVIDER_COST_MICROS, {**labels, "organization": origin.ORG.hex}) >= 0
    assert metrics.histogram(PROVIDER_SECONDS, labels).count == 1


class _Failing(ScriptedProvider):
    async def generate(self, request: GenerateRequest) -> GenerateResult:
        raise Error(ErrorCode.PROVIDER_UNAVAILABLE, "down")

    async def embed(self, request: EmbedRequest) -> EmbedResult:
        raise Error(ErrorCode.PROVIDER_QUOTA, "spent")


async def test_a_failure_is_counted_under_its_code_and_still_raised() -> None:
    metered, metrics = _metered(_Failing([]))
    with pytest.raises(Error):
        await metered.generate(_request())
    labels = {"capability": CAP, "model": MODEL, "outcome": "ai.provider.unavailable"}
    assert metrics.value(PROVIDER_CALLS, labels) == 1
    embed = EmbedRequest(
        organization_id=origin.ORG,
        capability="search",
        alias=ModelAlias.EMBED_DEFAULT,
        texts=["one"],
        timeout_ms=5000,
    )
    with pytest.raises(Error):
        await metered.embed(embed)
    quota = {"capability": "search", "model": MODEL, "outcome": "ai.provider.quota"}
    assert metrics.value(PROVIDER_CALLS, quota) == 1


async def test_an_embedding_and_the_delegated_methods_go_through() -> None:
    provider = ScriptedProvider([])
    metered, metrics = _metered(provider)
    embed = EmbedRequest(
        organization_id=origin.ORG,
        capability="search",
        alias=ModelAlias.EMBED_DEFAULT,
        texts=["one", "two"],
        timeout_ms=5000,
    )
    result = await metered.embed(embed)
    assert len(result.vectors) == 2
    assert (
        metrics.value(PROVIDER_CALLS, {"capability": "search", "model": MODEL, "outcome": "ok"})
        == 1
    )
    assert metered.model_id(ModelAlias.TEXT_DEFAULT) == MODEL
    assert metered.count_tokens(ModelAlias.TEXT_DEFAULT, "four words in here") > 0


async def test_a_stream_is_counted_once_with_the_usage_it_carried() -> None:
    metered, metrics = _metered(ScriptedProvider([GOOD]))
    frames = [frame async for frame in metered.stream(_request())]
    assert frames[-1].kind in {"done", "usage"}
    labels = {"capability": CAP, "model": MODEL}
    assert metrics.value(PROVIDER_CALLS, {**labels, "outcome": "ok"}) == 1
    assert metrics.histogram(PROVIDER_SECONDS, labels).count == 1
