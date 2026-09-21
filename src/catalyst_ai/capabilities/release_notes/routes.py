"""The one operation: typed in, typed out, no branch."""

from typing import Annotated

from fastapi import APIRouter, Header, Request

from catalyst_ai.capabilities.release_notes import descriptor
from catalyst_ai.capabilities.release_notes.pipeline import run
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.release_notes import ReleaseNotesRequest, ReleaseNotesResponse
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
    "/v1/release-notes",
    operation_id="release_notes.run",
    response_model=ReleaseNotesResponse,
    openapi_extra={
        "x-capability": descriptor.name,
        "x-capability-version": descriptor.version,
        "x-error-codes": [code.value for code in ERROR_CODES],
    },
)
async def release_notes(
    body: ReleaseNotesRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> ReleaseNotesResponse:
    """Write notes or an overview; every entry cites a change the backend sent."""
    return await run(body, request.app.state.runtime, request_id_of(request), idempotency_key)
