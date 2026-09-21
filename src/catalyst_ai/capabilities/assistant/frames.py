"""The turn's events become the contract's frames; a raised error becomes the terminal one."""

from collections.abc import AsyncIterator, Callable

from pydantic import BaseModel

from catalyst_ai.contract.assistant import TurnResponse
from catalyst_ai.contract.streaming import (
    CitationFrame,
    DeltaFrame,
    DoneFrame,
    ErrorFrame,
    UsageFrame,
)
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.pipeline import Event


def _citation_frames(response: TurnResponse) -> list[BaseModel]:
    return [CitationFrame(source=s) for s in response.sources]


async def frames_of(events: AsyncIterator[Event[TurnResponse]]) -> AsyncIterator[BaseModel]:
    """Deltas as they come; on completion the citations, the usage, then `done`."""
    async for event in events:
        if event.kind == "delta":
            yield DeltaFrame(text=event.text)
        elif event.kind == "usage" and event.usage is not None:
            yield UsageFrame(usage=event.usage)
        elif event.kind == "done" and event.result is not None:
            for frame in _citation_frames(event.result):
                yield frame
            yield DoneFrame(result=event.result)


def error_frame(request_id: str) -> Callable[[Error], BaseModel]:
    """Return the builder of the terminal `error` frame for this request."""

    def build(error: Error) -> BaseModel:
        return ErrorFrame(error=error.envelope(request_id))

    return build
