"""Server-sent events: one event per frame, the terminal frame ends it, an error becomes one."""

from collections.abc import AsyncIterator

import pytest
from pydantic import BaseModel

from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.httpserver.sse import UNTERMINATED, encode, events, stream_response


class Frame(BaseModel):
    """A stand-in frame with the one field the writer reads."""

    kind: str
    text: str | None = None


async def _frames(*kinds: str, raise_after: bool = False) -> AsyncIterator[BaseModel]:
    for kind in kinds:
        yield Frame(kind=kind, text="x" if kind == "delta" else None)
    if raise_after:
        raise Error(ErrorCode.PROVIDER_UNAVAILABLE, "gone")


def _on_error(error: Error) -> BaseModel:
    return Frame(kind="error", text=error.code.value)


async def _collect(frames: AsyncIterator[BaseModel]) -> list[str]:
    return [chunk.decode() async for chunk in events(frames, _on_error)]


def test_encode_names_the_event_after_the_kind_and_drops_nones() -> None:
    assert (
        encode(Frame(kind="delta", text="héllo"))
        == b'event: delta\ndata: {"kind": "delta", "text": "h\xc3\xa9llo"}\n\n'
    )
    assert encode(Frame(kind="done")) == b'event: done\ndata: {"kind": "done"}\n\n'


async def test_events_stop_at_the_terminal_frame() -> None:
    written = await _collect(_frames("delta", "usage", "done", "delta"))
    assert [line.split("\n")[0] for line in written] == [
        "event: delta",
        "event: usage",
        "event: done",
    ]


async def test_a_raised_error_becomes_the_terminal_frame() -> None:
    written = await _collect(_frames("delta", raise_after=True))
    assert (
        written[-1]
        == 'event: error\ndata: {"kind": "error", "text": "ai.provider.unavailable"}\n\n'
    )
    assert len(written) == 2


async def test_a_stream_without_a_terminal_frame_is_a_defect() -> None:
    with pytest.raises(RuntimeError, match=UNTERMINATED):
        await _collect(_frames("delta"))


def test_stream_response_is_an_uncached_event_stream_with_the_request_id() -> None:
    response = stream_response(_frames("done"), _on_error, "rid-1")
    assert response.media_type == "text/event-stream"
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-request-id"] == "rid-1"
