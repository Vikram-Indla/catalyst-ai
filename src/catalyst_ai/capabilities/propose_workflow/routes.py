"""The one operation: typed in, typed out, no branch."""

from typing import Annotated

from fastapi import APIRouter, Header, Request

from catalyst_ai.capabilities.propose_workflow import descriptor
from catalyst_ai.capabilities.propose_workflow.pipeline import run
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.propose_workflow import ProposeWorkflowRequest, ProposeWorkflowResponse
from catalyst_ai.platform.httpserver import request_id_of

ERROR_CODES = (
    ErrorCode.CONTRACT_VERSION_MISMATCH,
    ErrorCode.CAPABILITY_DISABLED,
    ErrorCode.INPUT_REJECTED,
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
    "/v1/propose-workflow",
    operation_id="propose_workflow.run",
    response_model=ProposeWorkflowResponse,
    openapi_extra={
        "x-capability": descriptor.name,
        "x-capability-version": descriptor.version,
        "x-error-codes": [code.value for code in ERROR_CODES],
    },
)
async def propose_workflow(
    body: ProposeWorkflowRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ProposeWorkflowResponse:
    """Propose a scheme; the backend validates it against its engine before installing anything."""
    return await run(body, request.app.state.runtime, request_id_of(request), idempotency_key)
