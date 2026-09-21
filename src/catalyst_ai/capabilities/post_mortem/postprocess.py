"""Stages 6 and 7: facts traced, tokens only, analysis apart from facts, the response."""

from typing import Final

from catalyst_ai.capabilities.post_mortem import descriptor
from catalyst_ai.capabilities.post_mortem.schema import ModelOutput, prose_of
from catalyst_ai.contract.post_mortem import (
    ActionItem,
    Fact,
    Factor,
    PostMortemRequest,
    PostMortemResponse,
)
from catalyst_ai.platform.language.records import (
    refuse_foreign_tokens,
    refuse_untraceable,
    tokens_in,
)
from catalyst_ai.platform.observability import ProviderCallRow, log_provider_call
from catalyst_ai.providers.port import GenerateResult

EMPTY: Final = "timeline_empty"
PENALTY_NO_FACTORS = 0.2
PENALTY_ACTIONS_WITHOUT_EVIDENCE = 0.1
PENALTY_SPARSE_FACTS = 0.1
SPARSE_SHARE = 0.5


def cited(output: ModelOutput) -> list[tuple[str, str]]:
    """Every (field, source id) pair the completion cites."""
    pairs = [(f"facts.{i}", f.source_id) for i, f in enumerate(output.facts)]
    pairs += [
        (f"contributing_factors.{i}", e)
        for i, f in enumerate(output.contributing_factors)
        for e in f.evidence
    ]
    return pairs + [
        (f"action_items.{i}", e) for i, a in enumerate(output.action_items) for e in a.evidence
    ]


def check_records(output: ModelOutput, request: PostMortemRequest) -> None:
    """Every citation names a timeline entry; no token the timeline did not carry."""
    refuse_untraceable(cited(output), {e.id for e in request.timeline})
    known = {e.participant for e in request.timeline if e.participant}
    refuse_foreign_tokens(prose_of(output), output.participants_mentioned, known, "summary")


def facts_of(output: ModelOutput, request: PostMortemRequest) -> list[Fact]:
    """Return the facts in the timeline's order, one per cited entry at most."""
    by_source: dict[str, str] = {}
    for fact in output.facts:
        if fact.text.strip() and fact.source_id not in by_source:
            by_source[fact.source_id] = fact.text.strip()
    return [
        Fact(source_id=e.id, text=by_source[e.id]) for e in request.timeline if e.id in by_source
    ]


def factors_of(output: ModelOutput) -> list[Factor]:
    """Return the factors that rest on at least one entry; analysis without evidence goes."""
    return [
        Factor(text=f.text.strip(), evidence=list(dict.fromkeys(f.evidence)))
        for f in output.contributing_factors
        if f.text.strip() and f.evidence
    ]


def actions_of(output: ModelOutput) -> list[ActionItem]:
    """Return the candidate actions with the model's confidence, evidence kept as given."""
    return [
        ActionItem(
            text=a.text.strip(), evidence=list(dict.fromkeys(a.evidence)), confidence=a.confidence
        )
        for a in output.action_items
        if a.text.strip()
    ]


def confidence(
    facts: list[Fact], factors: list[Factor], actions: list[ActionItem], total: int
) -> float:
    """Score deterministically: factors present, actions evidenced, enough of the timeline read."""
    score = 1.0
    if not factors:
        score -= PENALTY_NO_FACTORS
    if any(not a.evidence for a in actions):
        score -= PENALTY_ACTIONS_WITHOUT_EVIDENCE
    if total and len(facts) < total * SPARSE_SHARE:
        score -= PENALTY_SPARSE_FACTS
    return round(max(0.0, score), 2)


def to_response(
    output: ModelOutput, result: GenerateResult, request: PostMortemRequest, request_id: str
) -> PostMortemResponse:
    """Check the records, lay the facts out in order, log the row, build the response."""
    empty = output.empty_reason is not None or not request.timeline
    if not empty:
        check_records(output, request)
    facts = facts_of(output, request) if not empty else []
    factors = factors_of(output) if not empty else []
    actions = actions_of(output) if not empty else []
    log_provider_call(_row(result, request, request_id))
    return PostMortemResponse(
        capability_version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        model=f"{descriptor.alias}@{result.model_id}",
        eval_set_version=descriptor.eval_set_version,
        usage=result.usage,
        request_id=request_id,
        summary="" if empty else output.summary.strip(),
        facts=facts,
        contributing_factors=factors,
        action_items=actions,
        participants_mentioned=sorted(tokens_in(prose_of(output))) if not empty else [],
        empty_reason=EMPTY if empty else None,
        confidence=1.0 if empty else confidence(facts, factors, actions, len(request.timeline)),
    )


def _row(result: GenerateResult, request: PostMortemRequest, request_id: str) -> ProviderCallRow:
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


def from_cache(text: str, request_id: str) -> PostMortemResponse:
    """Rebuild a cached response under the new request id, marked as a hit and free."""
    cached = PostMortemResponse.model_validate_json(text)
    usage = cached.usage.model_copy(update={"cache_hit": True, "cost_micros": 0, "latency_ms": 0})
    return cached.model_copy(update={"request_id": request_id, "usage": usage})
