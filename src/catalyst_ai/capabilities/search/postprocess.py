"""Stage 7 for the three operations: the response models with versions, the usage row logged."""

from uuid import UUID

from catalyst_ai.capabilities.search import descriptor
from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.contract.search import (
    Hit,
    IndexDeleteResult,
    IndexedDocument,
    IndexUpsertResult,
    SearchRequest,
    SearchResponse,
)
from catalyst_ai.platform.observability import ProviderCallRow, log_provider_call
from catalyst_ai.retrieval import Found, UpsertOutcome
from catalyst_ai.retrieval.embeddings import NO_USAGE


def _row(organization_id: UUID, model_id: str, usage: Usage, request_id: str) -> ProviderCallRow:
    return ProviderCallRow(
        organization_id=organization_id,
        capability=descriptor.name,
        capability_version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        model_alias=descriptor.alias,
        model_id=model_id,
        input_tokens=usage.input_tokens,
        output_tokens=usage.output_tokens,
        cost_micros=usage.cost_micros,
        latency_ms=usage.latency_ms,
        cache_hit=usage.cache_hit,
        outcome="ok",
        request_id=request_id,
    )


def _model(model_id: str) -> str:
    return f"{descriptor.alias}@{model_id}"


def bare(hit: Hit) -> Hit:
    """Return the hit without its content: the key, the kind, the score and how it ranked."""
    return hit.model_copy(update={"title": None, "snippet": ""})


def to_response(found: Found, request: SearchRequest, request_id: str) -> SearchResponse:
    """Build the search response; the usage row is logged when the port was called."""
    if found.usage != NO_USAGE:
        log_provider_call(_row(request.organization_id, found.model_id, found.usage, request_id))
    return SearchResponse(
        capability_version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        model=_model(found.model_id),
        eval_set_version=descriptor.eval_set_version,
        usage=found.usage,
        request_id=request_id,
        hits=[bare(hit) for hit in found.hits] if request.ids_only else found.hits,
        fusion=found.fusion,
        embedding_version=found.embedding_version,
    )


def to_upsert_response(
    outcome: UpsertOutcome, organization_id: UUID, request_id: str
) -> IndexUpsertResult:
    """Build the upsert response; the usage row is logged when the port was called."""
    if outcome.usage != NO_USAGE:
        log_provider_call(_row(organization_id, outcome.model_id, outcome.usage, request_id))
    return IndexUpsertResult(
        capability_version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        model=_model(outcome.model_id),
        eval_set_version=descriptor.eval_set_version,
        usage=outcome.usage,
        request_id=request_id,
        results=[
            IndexedDocument(
                external_id=r.external_id,
                chunks=r.chunks,
                embedding_model=r.embedding_model,
                embedding_version=r.embedding_version,
                unchanged=r.unchanged,
            )
            for r in outcome.results
        ],
        index_chunks=outcome.index_chunks,
    )


def to_delete_response(deleted: int, model_id: str, request_id: str) -> IndexDeleteResult:
    """Build the delete response; nothing was embedded, the usage is empty."""
    return IndexDeleteResult(
        capability_version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        model=_model(model_id),
        eval_set_version=descriptor.eval_set_version,
        usage=NO_USAGE,
        request_id=request_id,
        deleted_chunks=deleted,
    )
