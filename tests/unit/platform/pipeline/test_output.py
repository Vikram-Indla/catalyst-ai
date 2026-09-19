"""The repair loop: one retry on invalid text, then ai.output.invalid; usage summed."""

import pytest
from pydantic import BaseModel

from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.pipeline import parse_with_repair
from catalyst_ai.platform.pipeline.output import merge_usage
from catalyst_ai.providers.port import GenerateResult


class Shape(BaseModel):
    a: int


def _result(text: str, cost: int = 5) -> GenerateResult:
    return GenerateResult(
        text=text,
        model_id="m",
        usage=Usage(
            input_tokens=1, output_tokens=1, cost_micros=cost, latency_ms=3, cache_hit=False
        ),
    )


async def test_valid_first_time() -> None:
    calls = 0

    async def repair() -> GenerateResult:
        nonlocal calls
        calls += 1
        return _result('{"a": 2}')

    shape, result = await parse_with_repair(_result('{"a": 1}'), Shape, repair)
    assert shape.a == 1
    assert calls == 0
    assert result.usage.cost_micros == 5


async def test_repaired_once_with_summed_usage() -> None:
    async def repair() -> GenerateResult:
        return _result('{"a": 2}', cost=7)

    shape, result = await parse_with_repair(_result("nope"), Shape, repair)
    assert shape.a == 2
    assert result.usage.cost_micros == 12
    assert result.usage.latency_ms == 6


async def test_refused_after_the_repair() -> None:
    async def repair() -> GenerateResult:
        return _result("still nope")

    with pytest.raises(Error) as caught:
        await parse_with_repair(_result("nope"), Shape, repair)
    assert caught.value.code is ErrorCode.OUTPUT_INVALID


def test_merge_usage_keeps_the_second_text() -> None:
    merged = merge_usage(_result("a", 1), _result("b", 2))
    assert merged.text == "b"
    assert merged.usage.cost_micros == 3
