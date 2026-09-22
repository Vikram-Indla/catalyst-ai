"""Ingest as a job: the submission runs the door and stores the row; the worker runs the rest.

Below the size line the synchronous operation is the right one (a small document embeds in
seconds); above it the synchronous path refuses and the job path holds no connection. The
worker parses the stored payload as the request model it always was — nothing else is trusted.
"""

from fastapi import Request
from pydantic import BaseModel, ValidationError

from catalyst_ai.capabilities.documents import descriptor
from catalyst_ai.capabilities.documents.ingest import admit_ingest, run_ingest
from catalyst_ai.contract.documents import IngestRequest
from catalyst_ai.contract.errors import ErrorCode, ErrorDetail
from catalyst_ai.contract.jobs import JobAccepted
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.jobs import submit
from catalyst_ai.platform.runtime import RuntimeContext

SYNC_MAX_BYTES = 256 * 1024
SIZE_FIELD = "content_base64"
SIZE_CODE = "use_the_job_operation"


def document_bytes(request: IngestRequest) -> int:
    """Return the decoded size of the document the request carries."""
    if request.content_base64 is not None:
        return len(request.content_base64) * 3 // 4
    return len(request.text or "")


def refuse_above_the_line(request: IngestRequest) -> None:
    """Refuse a document above the synchronous line; the job operation takes it instead."""
    if document_bytes(request) > SYNC_MAX_BYTES:
        detail = ErrorDetail(
            field=SIZE_FIELD,
            code=SIZE_CODE,
            message=f"documents above {SYNC_MAX_BYTES} bytes go through documents.ingest_job",
        )
        raise Error(
            ErrorCode.INPUT_TOO_LARGE,
            "the document is above the synchronous line",
            details=[detail],
        )


async def submit_ingest(
    body: IngestRequest, request: Request, runtime: RuntimeContext
) -> tuple[JobAccepted, str]:
    """Run the door synchronously, then store the verified request as a job."""
    admit_ingest(body, runtime)
    return await submit(request, descriptor.name, runtime.jobs, runtime.clock.now())


async def run_ingest_payload(payload: bytes, runtime: RuntimeContext, request_id: str) -> BaseModel:
    """Run the stored payload as the request model it always was, through the pipeline."""
    try:
        body = IngestRequest.model_validate_json(payload)
    except ValidationError as error:
        raise Error(
            ErrorCode.VALIDATION_INVALID_INPUT, "the stored payload is not the request"
        ) from error
    return await run_ingest(body, runtime, request_id)
