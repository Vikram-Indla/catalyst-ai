"""Stages 6 and 7: every sentence cited from the chain, no unseen number, then the response.

A sentence that cites no id, or an id the chain does not carry, is `ai.output.invalid`
(`untraceable_entry`); a number the chain does not carry is `ai.output.invalid`
(`unseen_number`). Both are refused rather than dropped, so a reader never gets a briefing that
silently lost a claim.
"""

from types import MappingProxyType
from typing import Final

from catalyst_ai.capabilities.brief import descriptor
from catalyst_ai.capabilities.brief.facts import ids_of, is_empty, unseen_numbers
from catalyst_ai.capabilities.brief.schema import ModelOutput, ModelSentence, prose_of, sentences_of
from catalyst_ai.contract.brief import BriefRequest, BriefResponse, CitedSentence
from catalyst_ai.contract.errors import ErrorCode, ErrorDetail
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.language.records import refuse_untraceable
from catalyst_ai.platform.observability import ProviderCallRow, log_provider_call
from catalyst_ai.providers.port import GenerateResult

NOTHING: Final = "nothing_to_brief"
EMPTY_NOTES: Final = MappingProxyType(
    {
        "en": "the chain carries no objective, project or finding",
        "ar": "لا تحمل السلسلة أي هدف أو مشروع أو ملاحظة",
    }
)
UNCITED: Final = "(none)"
UNSEEN: Final = "unseen_number"
PENALTY_NO_RISK_READ = 0.2
PENALTY_SHORT = 0.1


def cited(output: ModelOutput) -> list[tuple[str, str]]:
    """Every (field, id) pair the completion cites; a sentence citing nothing counts as one."""
    pairs = []
    for field, sentence in sentences_of(output):
        pairs += [(field, cite) for cite in sentence.cites] or [(field, UNCITED)]
    return pairs


def check_grounding(output: ModelOutput, request: BriefRequest) -> None:
    """Refuse an uncited sentence, a citation outside the chain, and a number the chain lacks."""
    refuse_untraceable(cited(output), ids_of(request.chain))
    unseen = unseen_numbers(prose_of(output), request.chain)
    if unseen:
        details = [ErrorDetail(field="summary", code=UNSEEN, message=f"{n:g}") for n in unseen]
        raise Error(
            ErrorCode.OUTPUT_INVALID,
            "the briefing states a number the chain does not carry",
            details=details,
        )


def _sentences(sentences: list[ModelSentence], limit: int) -> list[CitedSentence]:
    kept = [s for s in sentences if s.text.strip()]
    return [CitedSentence(text=s.text.strip(), cites=list(s.cites)) for s in kept[:limit]]


def confidence(output: ModelOutput, request: BriefRequest) -> float:
    """Score deterministically: a chain with trouble in it needs a risk, and the summary a body."""
    score = 1.0
    chain = request.chain
    troubled = any(o.status in ("at_risk", "off_track") for o in chain.objectives) or any(
        p.blocked or p.delivery_health == "off_track" for p in chain.projects
    )
    if troubled and not output.risks:
        score -= PENALTY_NO_RISK_READ
    if len(output.summary) < min(request.max_sentences, 2):
        score -= PENALTY_SHORT
    return round(max(0.0, score), 2)


def to_response(
    output: ModelOutput, result: GenerateResult, request: BriefRequest, request_id: str
) -> BriefResponse:
    """Check the grounding, log the row, build the response; an empty chain briefs nothing."""
    empty = is_empty(request.chain)
    if not empty:
        check_grounding(output, request)
    log_provider_call(_row(result, request, request_id))
    return BriefResponse(
        capability_version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        model=f"{descriptor.alias}@{result.model_id}",
        eval_set_version=descriptor.eval_set_version,
        usage=result.usage,
        request_id=request_id,
        summary=[] if empty else _sentences(output.summary, request.max_sentences),
        highlights=[] if empty else _sentences(output.highlights, 10),
        risks=[] if empty else _sentences(output.risks, 10),
        asks=[] if empty else _sentences(output.asks, 10),
        unsupported=[EMPTY_NOTES[request.locale]]
        if empty
        else [n.strip() for n in output.unsupported if n.strip()],
        empty_reason=NOTHING if empty else None,
        confidence=1.0 if empty else confidence(output, request),
    )


def _row(result: GenerateResult, request: BriefRequest, request_id: str) -> ProviderCallRow:
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


def from_cache(text: str, request_id: str) -> BriefResponse:
    """Rebuild a cached response under the new request id, marked as a hit and free."""
    cached = BriefResponse.model_validate_json(text)
    usage = cached.usage.model_copy(update={"cache_hit": True, "cost_micros": 0, "latency_ms": 0})
    return cached.model_copy(update={"request_id": request_id, "usage": usage})
