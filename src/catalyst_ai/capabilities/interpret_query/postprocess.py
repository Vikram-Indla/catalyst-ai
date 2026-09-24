"""Stage 7: the query written canonically, what it left out, the row, the cache."""

from catalyst_ai.capabilities.interpret_query import descriptor
from catalyst_ai.capabilities.interpret_query.grammar import canonical
from catalyst_ai.capabilities.interpret_query.schema import ModelOutput
from catalyst_ai.contract.interpret_query import InterpretQueryRequest, InterpretQueryResponse
from catalyst_ai.platform.observability import ProviderCallRow, log_provider_call
from catalyst_ai.providers.port import GenerateResult

PENALTY_UNRESOLVED = 0.2
PENALTY_EMPTY = 0.4


def confidence(query: str, unresolved: list[str]) -> float:
    """Score deterministically: a query was written; every term was placed."""
    score = 1.0
    if unresolved:
        score -= PENALTY_UNRESOLVED
    if not query:
        score -= PENALTY_EMPTY
    return round(max(0.0, score), 2)


def to_response(
    output: ModelOutput, result: GenerateResult, request: InterpretQueryRequest, request_id: str
) -> InterpretQueryResponse:
    """Write the checked query back canonically; log the content-free row."""
    log_provider_call(_row(result, request, request_id))
    query = canonical(output.query, request.grammar) if output.query.strip() else ""
    unresolved = output.terms()
    return InterpretQueryResponse(
        capability_version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        model=f"{descriptor.alias}@{result.model_id}",
        eval_set_version=descriptor.eval_set_version,
        usage=result.usage,
        request_id=request_id,
        query=query,
        explanation=output.explanation.strip(),
        unresolved=unresolved,
        confidence=confidence(query, unresolved),
    )


def _row(
    result: GenerateResult, request: InterpretQueryRequest, request_id: str
) -> ProviderCallRow:
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


def from_cache(text: str, request_id: str) -> InterpretQueryResponse:
    """Rebuild a cached response under the new request id, marked as a hit and free."""
    cached = InterpretQueryResponse.model_validate_json(text)
    usage = cached.usage.model_copy(update={"cache_hit": True, "cost_micros": 0, "latency_ms": 0})
    return cached.model_copy(update={"request_id": request_id, "usage": usage})
