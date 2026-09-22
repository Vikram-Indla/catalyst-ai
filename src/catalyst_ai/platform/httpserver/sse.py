"""Server-sent events: every frame is one event named by its kind; a stream always ends terminal.

The route hands over an async iterator of frames (pydantic models with a `kind`); this module
writes them, and when the iterator raises the catalog error it writes the `error` frame the
caller builds for it. Nothing after a terminal frame is ever written.
"""

import json
from collections.abc import AsyncIterator, Callable

from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.observability.metrics import ERRORS, Metrics

EVENT_STREAM = "text/event-stream"
NO_CACHE = "no-cache"
TERMINAL = frozenset({"done", "error"})
UNTERMINATED = "the stream ended without a terminal frame"


def encode(frame: BaseModel) -> bytes:
    """Render one frame as an event: the kind as the event name, the model as the data line."""
    kind = str(getattr(frame, "kind", ""))
    data = json.dumps(frame.model_dump(mode="json", exclude_none=True), ensure_ascii=False)
    return f"event: {kind}\ndata: {data}\n\n".encode()


async def events(
    frames: AsyncIterator[BaseModel],
    on_error: Callable[[Error], BaseModel],
    metrics: Metrics | None = None,
) -> AsyncIterator[bytes]:
    """Yield encoded frames until the terminal one; a raised error becomes the terminal frame."""
    try:
        async for frame in frames:
            yield encode(frame)
            _count(metrics, frame)
            if getattr(frame, "kind", "") in TERMINAL:
                return
    except Error as error:
        if metrics is not None:
            metrics.count(ERRORS, {"code": error.code.value})
        yield encode(on_error(error))
        return
    raise RuntimeError(UNTERMINATED)


def _count(metrics: Metrics | None, frame: BaseModel) -> None:
    """Count a terminal `error` frame by its code: a refusal like any other."""
    envelope = getattr(frame, "error", None)
    code = getattr(getattr(envelope, "error", None), "code", None)
    if metrics is not None and code is not None:
        metrics.count(ERRORS, {"code": str(code)})


def stream_response(
    frames: AsyncIterator[BaseModel],
    on_error: Callable[[Error], BaseModel],
    request_id: str,
    metrics: Metrics | None = None,
) -> StreamingResponse:
    """Return the response the route sends: an event stream that is never cached."""
    return StreamingResponse(
        events(frames, on_error, metrics),
        media_type=EVENT_STREAM,
        headers={"Cache-Control": NO_CACHE, "X-Request-Id": request_id},
    )
