"""The runner: parse, validate, assemble, call, validate_output, postprocess; cache in front."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import BaseModel

from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.providers.port import GenerateRequest, GenerateResult


@dataclass(frozen=True)
class Stages[Req: BaseModel, Parsed, Out, Res: BaseModel]:
    """A capability's seven stages, bound by name; the runner calls them in this order."""

    parse: Callable[[Req, str, str | None], Parsed]
    validate: Callable[[Parsed, RuntimeContext], str]
    assemble: Callable[[Parsed, RuntimeContext], GenerateRequest]
    call: Callable[[GenerateRequest, RuntimeContext], Awaitable[GenerateResult]]
    validate_output: Callable[
        [GenerateResult, GenerateRequest, Parsed, RuntimeContext],
        Awaitable[tuple[Out, GenerateResult]],
    ]
    postprocess: Callable[[Out, GenerateResult, Parsed, RuntimeContext], Res]
    from_cache: Callable[[str, str], Res]
    cache_ttl: Callable[[RuntimeContext], int]


async def run_stages[Req: BaseModel, Parsed, Out, Res: BaseModel](
    stages: Stages[Req, Parsed, Out, Res],
    request: Req,
    runtime: RuntimeContext,
    request_id: str,
    idempotency: str | None,
) -> Res:
    """Run the stages in order with the cache in front of the call."""
    parsed = stages.parse(request, request_id, idempotency)
    key = stages.validate(parsed, runtime)
    cached = runtime.cache.get(key)
    if cached is not None:
        return stages.from_cache(cached, request_id)
    generate = stages.assemble(parsed, runtime)
    result = await stages.call(generate, runtime)
    output, result = await stages.validate_output(result, generate, parsed, runtime)
    response = stages.postprocess(output, result, parsed, runtime)
    runtime.cache.set(key, response.model_dump_json(), stages.cache_ttl(runtime))
    return response
