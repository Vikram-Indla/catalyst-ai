"""The one operation: typed in, typed out, no branch."""

from typing import Annotated

from fastapi import APIRouter, Header, Request

from catalyst_ai.capabilities.generate_tests import descriptor
from catalyst_ai.capabilities.generate_tests.pipeline import run
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.generate_tests import GenerateTestsRequest, GenerateTestsResponse
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
    "/v1/generate-tests",
    operation_id="generate_tests.run",
    response_model=GenerateTestsResponse,
    openapi_extra={
        "x-capability": descriptor.name,
        "x-capability-version": descriptor.version,
        "x-error-codes": [code.value for code in ERROR_CODES],
    },
)
async def generate_tests(
    body: GenerateTestsRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> GenerateTestsResponse:
    """Write cases or artefacts; every one cites a criterion or a case the backend sent."""
    return await run(body, request.app.state.runtime, request_id_of(request), idempotency_key)
