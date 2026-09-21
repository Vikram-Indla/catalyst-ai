"""The response of a turn: the prose with its markers, the citations they resolve to, the row."""

from catalyst_ai.capabilities.assistant import descriptor
from catalyst_ai.capabilities.assistant.schema import Output, Tail
from catalyst_ai.capabilities.assistant.sources import Source, markers_of, sources_cited
from catalyst_ai.contract.assistant import TurnRequest, TurnResponse
from catalyst_ai.platform.observability import ProviderCallRow, log_provider_call
from catalyst_ai.providers.port import GenerateResult

PENALTY_NO_SOURCES = 0.2
PENALTY_UNCITED = 0.1


def confidence(prose: str, tail: Tail, sources: list[Source]) -> float:
    """Score deterministically: sources shown and cited; a not-found is certain of itself."""
    if tail.not_found:
        return 1.0
    score = 1.0
    if not sources:
        score -= PENALTY_NO_SOURCES
    elif not markers_of(prose):
        score -= PENALTY_UNCITED
    return round(max(0.0, score), 2)


def to_response(
    output: Output,
    result: GenerateResult,
    sources: list[Source],
    request: TurnRequest,
    request_id: str,
) -> TurnResponse:
    """Lay the turn out; log the content-free row."""
    log_provider_call(_row(result, request, request_id))
    prose, tail = output.prose, output.tail
    return TurnResponse(
        capability_version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        model=f"{descriptor.alias}@{result.model_id}",
        eval_set_version=descriptor.eval_set_version,
        usage=result.usage,
        request_id=request_id,
        reply=prose,
        sources=sources_cited(prose, sources),
        not_found=tail.not_found,
        confidence=confidence(prose, tail, sources),
    )


def _row(result: GenerateResult, request: TurnRequest, request_id: str) -> ProviderCallRow:
    return ProviderCallRow(
        organization_id=request.organization_id,
        capability=descriptor.name,
        capability_version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        model_alias=descriptor.alias,
        model_id=result.model_id,
        input_tokens=result.usage.input_tokens,
        output_tokens=result.usage.output_tokens,
        cost_micros=result.usage.cost_micros,
        latency_ms=result.usage.latency_ms,
        cache_hit=False,
        outcome="ok",
        request_id=request_id,
    )


def from_cache(text: str, request_id: str) -> TurnResponse:
    """Rebuild a cached response under the new request id, marked as a hit and free."""
    cached = TurnResponse.model_validate_json(text)
    usage = cached.usage.model_copy(update={"cache_hit": True, "cost_micros": 0, "latency_ms": 0})
    return cached.model_copy(update={"request_id": request_id, "usage": usage})
