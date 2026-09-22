"""The three operations: typed in, typed out, no branch."""

from fastapi import APIRouter, Request

from catalyst_ai.capabilities.search import descriptor
from catalyst_ai.capabilities.search.indexing import run_delete, run_upsert
from catalyst_ai.capabilities.search.pipeline import run
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.search import (
    IndexDeleteRequest,
    IndexDeleteResult,
    IndexUpsertRequest,
    IndexUpsertResult,
    SearchRequest,
    SearchResponse,
)
from catalyst_ai.platform.httpserver import request_id_of

COMMON_ERROR_CODES = (
    ErrorCode.CONTRACT_VERSION_MISMATCH,
    ErrorCode.CAPABILITY_DISABLED,
    ErrorCode.INPUT_REJECTED,
    ErrorCode.INPUT_TOO_LARGE,
    ErrorCode.BUDGET_EXCEEDED,
    ErrorCode.INDEX_UNAVAILABLE,
)
PROVIDER_ERROR_CODES = (
    ErrorCode.PROVIDER_UNAVAILABLE,
    ErrorCode.PROVIDER_TIMEOUT,
    ErrorCode.PROVIDER_REJECTED,
    ErrorCode.PROVIDER_QUOTA,
)
UPSERT_ERROR_CODES = (
    *COMMON_ERROR_CODES,
    ErrorCode.INDEX_DOCUMENT_TOO_LARGE,
    *PROVIDER_ERROR_CODES,
)
DELETE_ERROR_CODES = COMMON_ERROR_CODES
SEARCH_ERROR_CODES = (*COMMON_ERROR_CODES, *PROVIDER_ERROR_CODES)
router = APIRouter(tags=["capabilities"])


def _extra(codes: tuple[ErrorCode, ...]) -> dict[str, object]:
    return {
        "x-capability": descriptor.name,
        "x-capability-version": descriptor.version,
        "x-error-codes": [code.value for code in codes],
    }


@router.post(
    "/v1/index/upsert",
    operation_id="index.upsert",
    response_model=IndexUpsertResult,
    openapi_extra=_extra(UPSERT_ERROR_CODES),
)
async def index_upsert(body: IndexUpsertRequest, request: Request) -> IndexUpsertResult:
    """Index or re-index documents of the caller's organisation; unchanged hashes cost nothing."""
    return await run_upsert(body, request.app.state.runtime, request_id_of(request))


@router.post(
    "/v1/index/delete",
    operation_id="index.delete",
    response_model=IndexDeleteResult,
    openapi_extra=_extra(DELETE_ERROR_CODES),
)
async def index_delete(body: IndexDeleteRequest, request: Request) -> IndexDeleteResult:
    """Forget documents by key."""
    return await run_delete(body, request.app.state.runtime, request_id_of(request))


@router.post(
    "/v1/search",
    operation_id="search.run",
    response_model=SearchResponse,
    openapi_extra=_extra(SEARCH_ERROR_CODES),
)
async def search_run(body: SearchRequest, request: Request) -> SearchResponse:
    """Find similar or matching documents in one corpus of the caller's organisation."""
    return await run(body, request.app.state.runtime, request_id_of(request))
