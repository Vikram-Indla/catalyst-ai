"""The ingest operation: bounded parse, the class rule, structured windows, the shared index."""

import base64
import binascii

from catalyst_ai.capabilities.documents import descriptor
from catalyst_ai.contract.documents import DocumentFormat, IngestRequest, IngestResponse
from catalyst_ai.contract.errors import ErrorCode, ErrorDetail
from catalyst_ai.contract.search import IndexDocument
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.pipeline import Door, admit
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.platform.safety.input import ReasonClass, scan_fields
from catalyst_ai.retrieval import DOCUMENTS, Job, document_key, upsert, windows_of
from catalyst_ai.retrieval.parsers import Parsed, ParserError, Reason, parse
from catalyst_ai.retrieval.runner import parse_document

TEXT_FORMATS = frozenset({DocumentFormat.MARKDOWN, DocumentFormat.TEXT})
MS_PER_SECOND = 1_000
CHECK_FIELD = "document"


def _refuse(reason: Reason, message: str) -> Error:
    detail = ErrorDetail(field="content", code=reason.value, message=message)
    return Error(ErrorCode.INPUT_REJECTED, "the document was refused", details=[detail])


def payload_of(request: IngestRequest) -> bytes:
    """Return the bytes to parse: decoded base64, or the supplied text encoded."""
    if request.text is not None:
        return request.text.encode("utf-8")
    try:
        return base64.b64decode(request.content_base64 or "", validate=True)
    except (binascii.Error, ValueError) as error:
        raise _refuse(Reason.MALFORMED, "the bytes are not valid base64") from error


def refuse_restricted(parsed: Parsed) -> None:
    """Refuse RESTRICTED patterns in the extracted text; the rest inherits the declared class."""
    text = "\n".join(block.text for block in parsed.blocks)
    details = [d for d in scan_fields({CHECK_FIELD: text}) if d.code != ReasonClass.TOO_LARGE]
    if details:
        raise _refuse(Reason.RESTRICTED, f"the extracted text {details[0].message}")


async def parse_request(request: IngestRequest, runtime: RuntimeContext) -> Parsed:
    """Text formats parse in process; bytes parse in the bounded child; a refusal is a class."""
    payload = payload_of(request)
    timeout_ms = runtime.settings.capability_documents.timeout_ms or descriptor.timeout_ms
    try:
        if request.format in TEXT_FORMATS:
            return parse(request.format.value, payload)
        return await parse_document(request.format.value, payload, timeout_ms / MS_PER_SECOND)
    except ParserError as error:
        raise _refuse(error.reason, error.message) from error


def admit_ingest(request: IngestRequest, runtime: RuntimeContext) -> None:
    """Run the door for ingest: switch, version, tenant cap; the text is checked after parsing."""
    door = Door(
        name=descriptor.name,
        version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        alias=descriptor.alias,
        settings=runtime.settings.capability_documents,
        organization_id=request.organization_id,
        capability_version=request.capability_version,
        user_texts={"title": request.title},
        canonical_input={},
        idempotency=None,
    )
    admit(door, runtime)


def job_for(request: IngestRequest, runtime: RuntimeContext) -> Job:
    """Build the tenant, corpus and limits the indexing runs under."""
    return Job(
        organization_id=request.organization_id,
        spec=DOCUMENTS,
        capability=descriptor.name,
        timeout_ms=runtime.settings.capability_documents.timeout_ms or descriptor.timeout_ms,
        max_chunks=runtime.settings.retrieval_index_max_chunks_per_organization,
    )


async def run_ingest(
    request: IngestRequest, runtime: RuntimeContext, request_id: str
) -> IngestResponse:
    """Door, bounded parse, the class rule, structured windows, one embedding pass, the index."""
    admit_ingest(request, runtime)
    parsed = await parse_request(request, runtime)
    refuse_restricted(parsed)
    windows = windows_of(parsed, DOCUMENTS)
    document = IndexDocument(
        external_id=document_key(request.space_id, request.document_id),
        kind=request.kind,
        title=request.title,
        text="\n\n".join(block.text for block in parsed.blocks) or " ",
        data_class=request.data_class,
        content_hash=request.content_hash,
    )
    outcome = await upsert(
        job_for(request, runtime),
        [document],
        runtime.storage,
        runtime.provider,
        lambda _t, _s: windows,
    )
    result = outcome.results[0]
    return IngestResponse(
        capability_version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        model=f"{DOCUMENTS.alias.value}@{outcome.model_id}",
        eval_set_version=descriptor.eval_set_version,
        usage=outcome.usage,
        request_id=request_id,
        document_id=request.document_id,
        state="unchanged" if result.unchanged else "indexed",
        chunks=result.chunks,
        headings=parsed.headings,
        embedding_model=result.embedding_model,
        embedding_version=result.embedding_version,
        index_chunks=outcome.index_chunks,
    )
