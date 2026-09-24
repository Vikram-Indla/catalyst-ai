"""The one operation: typed in, typed out, no branch."""

from typing import Annotated

from fastapi import APIRouter, Header, Request

from catalyst_ai.capabilities.interpret_query import descriptor
from catalyst_ai.capabilities.interpret_query.pipeline import run
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.interpret_query import InterpretQueryRequest, InterpretQueryResponse
from catalyst_ai.platform.httpserver import request_id_of

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
)
router = APIRouter(tags=["capabilities"])


@router.post(
    "/v1/interpret-query",
    operation_id="interpret_query.run",
    response_model=InterpretQueryResponse,
    openapi_extra={
        "x-capability": descriptor.name,
        "x-capability-version": descriptor.version,
        "x-error-codes": [code.value for code in ERROR_CODES],
    },
)
async def interpret_query(
    body: InterpretQueryRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> InterpretQueryResponse:
    """Turn a sentence into a query in the grammar sent with it; nothing outside it is written."""
    return await run(body, request.app.state.runtime, request_id_of(request), idempotency_key)
