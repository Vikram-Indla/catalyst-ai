"""Events become frames: deltas, then the citations, the usage and `done`; an error frame."""

from collections.abc import AsyncIterator

from catalyst_ai.capabilities.assistant.frames import error_frame, frames_of
from catalyst_ai.capabilities.assistant.pipeline import run
from catalyst_ai.contract.assistant import TurnResponse
from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.streaming import CitationFrame, DoneFrame, ErrorFrame
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.pipeline import Event
from tests.unit.capabilities.assistant.conftest import ITEM_REPLY, turn_request
from tests.unit.capabilities.improve_story.conftest import ScriptedProvider, make_runtime

USAGE = Usage(input_tokens=1, output_tokens=1, cost_micros=1, latency_ms=1, cache_hit=False)


async def _events(response: TurnResponse) -> AsyncIterator[Event[TurnResponse]]:
    yield Event(kind="delta", text="The ")
    yield Event(kind="delta", text="button. [1]")
    yield Event(kind="usage", usage=USAGE)
    yield Event(kind="done", result=response)


async def test_frames_follow_the_events_and_carry_the_citations_before_done() -> None:
    response = await run(turn_request(), make_runtime(ScriptedProvider([ITEM_REPLY])), "r")
    frames = [f async for f in frames_of(_events(response))]
    kinds = [getattr(f, "kind", "") for f in frames]
    assert kinds == ["delta", "delta", "usage", "citation", "done"]
    citation, done = frames[3], frames[4]
    assert isinstance(citation, CitationFrame)
    assert citation.source.source_id == "item-41"
    assert isinstance(done, DoneFrame)
    assert done.result is response


def test_error_frame_carries_the_envelope_under_the_request_id() -> None:
    frame = error_frame("rid-7")(Error(ErrorCode.BUDGET_EXCEEDED, "spent"))
    assert isinstance(frame, ErrorFrame)
    assert frame.error.request_id == "rid-7"
    assert frame.error.error.code is ErrorCode.BUDGET_EXCEEDED
