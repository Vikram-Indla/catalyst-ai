"""The two index operations: the door, then the retrieval package does the work."""

from catalyst_ai.capabilities.search import descriptor
from catalyst_ai.capabilities.search.pipeline import timeout_ms
from catalyst_ai.capabilities.search.postprocess import to_delete_response, to_upsert_response
from catalyst_ai.contract.envelopes import RequestEnvelope
from catalyst_ai.contract.search import (
    Corpus,
    IndexDeleteRequest,
    IndexDeleteResult,
    IndexUpsertRequest,
    IndexUpsertResult,
)
from catalyst_ai.platform.pipeline import Door, admit
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.retrieval import Job, delete, spec_of, upsert
from catalyst_ai.retrieval.chunking import embedding_input


def admit_index(
    request: RequestEnvelope, user_texts: dict[str, str | None], runtime: RuntimeContext
) -> None:
    """Run the door for an index operation: switch, version, scanner over every text, cap."""
    door = Door(
        name=descriptor.name,
        version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        alias=descriptor.alias,
        settings=runtime.settings.capability_search,
        organization_id=request.organization_id,
        capability_version=request.capability_version,
        user_texts=user_texts,
        canonical_input={},
        idempotency=None,
    )
    admit(door, runtime)


def job_for(request: RequestEnvelope, corpus: Corpus, runtime: RuntimeContext) -> Job:
    """Build the tenant, corpus and limits an indexing call runs under."""
    return Job(
        organization_id=request.organization_id,
        spec=spec_of(corpus),
        capability=descriptor.name,
        timeout_ms=timeout_ms(runtime),
        max_chunks=runtime.settings.retrieval_index_max_chunks_per_organization,
    )


async def run_upsert(
    request: IndexUpsertRequest, runtime: RuntimeContext, request_id: str
) -> IndexUpsertResult:
    """Index the documents: door, budget, chunk, embed, store; unchanged ones are touched."""
    texts: dict[str, str | None] = {
        document.external_id: embedding_input(document.title, document.text)
        for document in request.documents
    }
    admit_index(request, texts, runtime)
    outcome = await upsert(
        job_for(request, request.corpus, runtime),
        request.documents,
        runtime.storage,
        runtime.provider,
    )
    return to_upsert_response(outcome, request.organization_id, request_id)


async def run_delete(
    request: IndexDeleteRequest, runtime: RuntimeContext, request_id: str
) -> IndexDeleteResult:
    """Forget the keys: door, then the delete."""
    admit_index(request, {}, runtime)
    job = job_for(request, request.corpus, runtime)
    deleted = await delete(job, request.external_ids, runtime.storage)
    return to_delete_response(deleted, runtime.provider.model_id(job.spec.alias), request_id)
