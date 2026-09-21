"""The three operations of one concern: typed in, typed out, no branch."""

from typing import Annotated

from fastapi import APIRouter, Header, Request

from catalyst_ai.capabilities.documents import descriptor
from catalyst_ai.capabilities.documents.ask import run as run_ask
from catalyst_ai.capabilities.documents.drafting import run as run_draft
from catalyst_ai.capabilities.documents.ingest import run_ingest
from catalyst_ai.contract.documents import (
    AskRequest,
    AskResponse,
    DraftRequest,
    DraftResponse,
    IngestRequest,
    IngestResponse,
)
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.httpserver import request_id_of

INGEST_ERROR_CODES = (
    ErrorCode.CONTRACT_VERSION_MISMATCH,
    ErrorCode.CAPABILITY_DISABLED,
    ErrorCode.INPUT_REJECTED,
    ErrorCode.BUDGET_EXCEEDED,
    ErrorCode.PROVIDER_UNAVAILABLE,
    ErrorCode.PROVIDER_TIMEOUT,
    ErrorCode.PROVIDER_REJECTED,
    ErrorCode.PROVIDER_QUOTA,
    ErrorCode.INDEX_DOCUMENT_TOO_LARGE,
    ErrorCode.INDEX_UNAVAILABLE,
)
ASK_ERROR_CODES = (
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
    ErrorCode.INDEX_UNAVAILABLE,
)
GENERATE_ERROR_CODES = (
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


def _extra(codes: tuple[ErrorCode, ...]) -> dict[str, object]:
    return {
        "x-capability": descriptor.name,
        "x-capability-version": descriptor.version,
        "x-error-codes": [code.value for code in codes],
    }


@router.post(
    "/v1/documents/ingest",
    operation_id="documents.ingest",
    response_model=IngestResponse,
    openapi_extra=_extra(INGEST_ERROR_CODES),
)
async def ingest(body: IngestRequest, request: Request) -> IngestResponse:
    """Parse a document under limits and index it in its space."""
    return await run_ingest(body, request.app.state.runtime, request_id_of(request))


@router.post(
    "/v1/documents/ask",
    operation_id="documents.ask",
    response_model=AskResponse,
    openapi_extra=_extra(ASK_ERROR_CODES),
)
async def ask(
    body: AskRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> AskResponse:
    """Answer only from the space's passages, every claim cited, or say not found."""
    return await run_ask(body, request.app.state.runtime, request_id_of(request), idempotency_key)


@router.post(
    "/v1/documents/generate",
    operation_id="documents.generate",
    response_model=DraftResponse,
    openapi_extra=_extra(GENERATE_ERROR_CODES),
)
async def generate(
    body: DraftRequest,
    request: Request,
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
) -> DraftResponse:
    """Draft from the supplied sources, every section citing what it rests on."""
    return await run_draft(body, request.app.state.runtime, request_id_of(request), idempotency_key)
