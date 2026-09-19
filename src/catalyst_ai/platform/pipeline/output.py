"""Stage 6 for every capability: parse against the schema with one repair, then the leakage scan."""

import json
from collections.abc import Awaitable, Callable

from pydantic import BaseModel, ValidationError

from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from catalyst_ai.providers.port import GenerateResult

REPAIR_ATTEMPTS = 1


def merge_usage(first: GenerateResult, second: GenerateResult) -> GenerateResult:
    """Return the second result carrying the summed usage of both calls."""
    usage = second.usage.model_copy(
        update={
            "input_tokens": first.usage.input_tokens + second.usage.input_tokens,
            "output_tokens": first.usage.output_tokens + second.usage.output_tokens,
            "cost_micros": first.usage.cost_micros + second.usage.cost_micros,
            "latency_ms": first.usage.latency_ms + second.usage.latency_ms,
        }
    )
    return second.model_copy(update={"usage": usage})


async def parse_with_repair[T: BaseModel](
    result: GenerateResult, schema: type[T], repair: Callable[[], Awaitable[GenerateResult]]
) -> tuple[T, GenerateResult]:
    """Validate the completion; on failure call once more; then `ai.output.invalid`."""
    attempts = 0
    current = result
    while True:
        try:
            return schema.model_validate(json.loads(current.text)), current
        except (ValidationError, ValueError) as error:
            attempts += 1
            if attempts > REPAIR_ATTEMPTS:
                raise Error(
                    ErrorCode.OUTPUT_INVALID, "the completion did not match the schema"
                ) from error
            current = merge_usage(current, await repair())
