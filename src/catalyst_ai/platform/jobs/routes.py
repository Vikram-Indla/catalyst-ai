"""`jobs.get`: the backend polls a job it submitted; anything else is not found."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.jobs import JobStatus
from catalyst_ai.platform.httpserver import request_id_of
from catalyst_ai.platform.jobs.submit import RETRY_AFTER_MS, read, status_of

CAPABILITY = "jobs"
VERSION = "1.0.0"
ERROR_CODES = (ErrorCode.JOB_NOT_FOUND,)
router = APIRouter(tags=["jobs"])


@router.get(
    "/v1/jobs/{job_id}",
    operation_id="jobs.get",
    response_model=JobStatus,
    openapi_extra={
        "x-capability": CAPABILITY,
        "x-capability-version": VERSION,
        "x-error-codes": [code.value for code in ERROR_CODES],
    },
)
async def get_job(
    job_id: UUID,
    request: Request,
    organization_id: Annotated[UUID, Query(description="The tenant the job belongs to")],
) -> JSONResponse:
    """Return the job's state with `Retry-After` until it is final, then its result or error."""
    row = await read(request, request.app.state.runtime.jobs, organization_id, job_id)
    status = status_of(row, request_id_of(request))
    headers = {} if status.retry_after_ms is None else {"Retry-After": str(RETRY_AFTER_MS // 1000)}
    return JSONResponse(content=status.model_dump(mode="json", exclude_none=True), headers=headers)
