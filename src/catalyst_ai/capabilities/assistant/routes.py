"""The two operations of one concern: a turn streamed as frames, or answered whole."""

from typing import Annotated

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse

from catalyst_ai.capabilities.assistant import descriptor
from catalyst_ai.capabilities.assistant.frames import error_frame, frames_of
from catalyst_ai.capabilities.assistant.pipeline import run, stream
from catalyst_ai.contract.assistant import TurnRequest, TurnResponse
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.streaming import StreamEnvelope
from catalyst_ai.platform.httpserver import request_id_of, stream_response

ERROR_CODES = (
    ErrorCode.CONTRACT_VERSION_MISMATCH,
    ErrorCode.CAPABILITY_DISABLED,
    ErrorCode.INPUT_REJECTED,
    ErrorCode.INPUT_TOO_LARGE,
    ErrorCode.BUDGET_EXCEEDED,
    ErrorCode.PROVIDER_UNAVAILABLE,
    ErrorCode.PROVIDER_TIMEOUT,
    ErrorCode.PROVIDER_REJECTED,
    ErrorCode.PROVIDER_QUOTA,
    ErrorCode.OUTPUT_INVALID,
    ErrorCode.OUTPUT_UNSAFE,
    ErrorCode.INDEX_UNAVAILABLE,
)
EVENT_STREAM = "text/event-stream"
STREAM_DESCRIPTION = "An event stream: `delta`*, `citation`*, `usage`, then `done` or `error`."
STREAM_EXAMPLE = (
    'event: delta\ndata: {"kind": "delta", "text": "The rollback needs approval. [1]"}\n\n'
    'event: usage\ndata: {"kind": "usage", "usage": {...}}\n\n'
    'event: done\ndata: {"kind": "done", "result": {...}}\n\n'
)
router = APIRouter(tags=["capabilities"])


def _extra() -> dict[str, object]:
    return {
        "x-capability": descriptor.name,
        "x-capability-version": descriptor.version,
        "x-error-codes": [code.value for code in ERROR_CODES],
    }


def _stream_responses() -> dict[int | str, dict[str, object]]:
    return {
        200: {
            "description": STREAM_DESCRIPTION,
            "model": StreamEnvelope,
            "content": {EVENT_STREAM: {"schema": {"type": "string"}, "example": STREAM_EXAMPLE}},
            "x-example": STREAM_EXAMPLE,
        }
    }


@router.post(
    "/v1/assistant/turn:stream",
    operation_id="assistant.turn",
    response_class=StreamingResponse,
    responses=_stream_responses(),
    openapi_extra=_extra(),
)
async def turn(body: TurnRequest, request: Request) -> StreamingResponse:
    """Answer one turn as typed frames; every stream ends with `done` or `error`."""
    request_id = request_id_of(request)
    events = stream(body, request.app.state.runtime, request_id)
    return stream_response(frames_of(events), error_frame(request_id), request_id)


@router.post(
    "/v1/assistant/turn",
    operation_id="assistant.turn_sync",
    response_model=TurnResponse,
    openapi_extra=_extra(),
)
async def turn_sync(
    body: TurnRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> TurnResponse:
    """Answer one turn whole — the same reply the stream ends with."""
    return await run(body, request.app.state.runtime, request_id_of(request), idempotency_key)
