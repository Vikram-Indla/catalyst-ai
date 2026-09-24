"""Two operations: one text now, or a batch of record fields as Arabic drafts, as a job."""

from typing import Annotated

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse

from catalyst_ai.capabilities.translate import descriptor
from catalyst_ai.capabilities.translate.jobs import submit_drafts
from catalyst_ai.capabilities.translate.pipeline import run
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.jobs import JobAccepted
from catalyst_ai.contract.translate import TranslateRequest, TranslateResponse
from catalyst_ai.contract.translate_drafts import DraftsRequest
from catalyst_ai.platform.httpserver import request_id_of
from catalyst_ai.platform.jobs import accepted_response

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
DRAFTS_JOB_ERROR_CODES = (
    ErrorCode.CONTRACT_VERSION_MISMATCH,
    ErrorCode.CAPABILITY_DISABLED,
    ErrorCode.INPUT_REJECTED,
    ErrorCode.BUDGET_EXCEEDED,
    ErrorCode.AUTH_ORIGIN_INVALID,
)
router = APIRouter(tags=["capabilities"])


@router.post(
    "/v1/translate",
    operation_id="translate.run",
    response_model=TranslateResponse,
    openapi_extra={
        "x-capability": descriptor.name,
        "x-capability-version": descriptor.version,
        "x-error-codes": [code.value for code in ERROR_CODES],
    },
)
async def translate(
    body: TranslateRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> TranslateResponse:
    """Translate a field or a title into the named target; structure and identifiers kept."""
    return await run(body, request.app.state.runtime, request_id_of(request), idempotency_key)


@router.post(
    "/v1/translate/drafts:jobs",
    operation_id="translate.drafts_job",
    status_code=202,
    response_model=JobAccepted,
    openapi_extra={
        "x-capability": descriptor.name,
        "x-capability-version": descriptor.version,
        "x-error-codes": [code.value for code in DRAFTS_JOB_ERROR_CODES],
    },
)
async def drafts_job(body: DraftsRequest, request: Request) -> JSONResponse:
    """Accept a batch of record fields as a job: Arabic drafts, never reviewed, per item."""
    accepted, location = await submit_drafts(body, request, request.app.state.runtime)
    return accepted_response(accepted, location)
