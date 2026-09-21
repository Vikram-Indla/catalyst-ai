"""The streaming runner: the same stages, the call replaced by the provider's frames.

Events leave in order — `delta` as the visible prose grows, `usage` once, then `done` with the
validated response — or the run raises the catalog error, which the route turns into the
terminal `error` frame. Deltas show only what `visible` allows: a capability whose completion
ends in a structured tail keeps the tail out of the stream and out of sight.
"""

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel

from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.platform.pipeline.stages import Stages
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.providers.port import GenerateResult

EventKind = Literal["delta", "usage", "done"]


@dataclass(frozen=True)
class Event[Res: BaseModel]:
    """One thing the runner has to say: a piece of prose, the usage, or the finished response."""

    kind: EventKind
    text: str = ""
    usage: Usage | None = None
    result: Res | None = None


def hold_back(text: str, marker: str) -> str:
    """Return the prefix of `text` that cannot be the start of `marker` cut short at the end.

    The whole marker present → everything before it. Otherwise the longest tail that is a
    proper prefix of the marker is held, so a marker split across two deltas never leaks.
    """
    cut = text.find(marker)
    if cut >= 0:
        return text[:cut]
    for length in range(min(len(marker) - 1, len(text)), 0, -1):
        if text.endswith(marker[:length]):
            return text[:-length]
    return text


async def run_streaming[Req: BaseModel, Parsed, Out, Res: BaseModel](
    stages: Stages[Req, Parsed, Out, Res],
    request: Req,
    runtime: RuntimeContext,
    request_id: str,
    visible: Callable[[str], str],
) -> AsyncIterator[Event[Res]]:
    """Run the stages with the provider streaming; no cache in front (a turn is not idempotent)."""
    parsed = stages.parse(request, request_id, None)
    stages.validate(parsed, runtime)
    if stages.retrieve is not None:
        parsed = await stages.retrieve(parsed, runtime)
    settled = stages.settle(parsed, runtime) if stages.settle is not None else None
    if settled is not None:
        yield Event(kind="done", result=settled)
        return
    generate = stages.assemble(parsed, runtime)
    pieces: list[str] = []
    shown = 0
    usage: Usage | None = None
    model_id = ""
    async for frame in runtime.provider.stream(generate):
        if frame.kind == "delta":
            pieces.append(frame.text)
            prose = visible("".join(pieces))
            if len(prose) > shown:
                yield Event(kind="delta", text=prose[shown:])
                shown = len(prose)
        elif frame.kind == "usage" and frame.usage is not None:
            usage = frame.usage
            model_id = frame.model_id or model_id
        elif frame.kind == "done":
            model_id = frame.model_id or model_id
    result = GenerateResult(
        text="".join(pieces),
        model_id=model_id,
        usage=usage
        or Usage(input_tokens=0, output_tokens=0, cost_micros=0, latency_ms=0, cache_hit=False),
    )
    output, result = await stages.validate_output(result, generate, parsed, runtime)
    response = stages.postprocess(output, result, parsed, runtime)
    yield Event(kind="usage", usage=result.usage)
    yield Event(kind="done", result=response)
