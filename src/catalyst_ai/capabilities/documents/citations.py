"""Stage 7 of ask: every claim cites a retrieved passage or the answer is refused; the response."""

from typing import Final

from catalyst_ai.capabilities.documents import descriptor
from catalyst_ai.capabilities.documents.schema import AskOutput, ModelClaim
from catalyst_ai.contract.documents import MAX_QUOTE, AskRequest, AskResponse, Citation
from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.contract.errors import ErrorCode, ErrorDetail
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.language.records import refuse_untraceable
from catalyst_ai.platform.observability import ProviderCallRow, log_provider_call
from catalyst_ai.providers.port import GenerateResult
from catalyst_ai.retrieval import Passage, Retrieved

UNCITED: Final = "uncited_claim"
NOT_FOUND_TEXT: Final = ""
PENALTY_WEAK_PASSAGES = 0.2
PENALTY_FEW_CLAIMS = 0.1
STRONG_SCORE = 0.5


def check_claims(output: AskOutput, passages: list[Passage]) -> None:
    """Every claim names a passage that was retrieved; a claim without one refuses the answer."""
    uncited = [
        ErrorDetail(field=f"claims.{i}", code=UNCITED, message="no passage behind the claim")
        for i, claim in enumerate(output.claims)
        if claim.text.strip() and not claim.chunk_ids
    ]
    if uncited:
        raise Error(ErrorCode.OUTPUT_INVALID, "an answer sentence cites nothing", details=uncited)
    cited = [(f"claims.{i}", c) for i, claim in enumerate(output.claims) for c in claim.chunk_ids]
    refuse_untraceable(cited, {p.chunk_id for p in passages})


def quote_for(passage: Passage, claim: str) -> str:
    """Return the passage's opening words; the part the claim rests on is not guessed at."""
    words = passage.text.split()
    quote = ""
    for word in words:
        if len(quote) + len(word) + 1 > MAX_QUOTE:
            break
        quote = f"{quote} {word}".strip()
    return quote or passage.text[:MAX_QUOTE]


def citations_of(output: AskOutput, passages: list[Passage]) -> list[Citation]:
    """One citation per distinct passage cited, in the order first cited."""
    by_id = {p.chunk_id: p for p in passages}
    seen: dict[str, Citation] = {}
    for claim in output.claims:
        for chunk in claim.chunk_ids:
            if chunk not in seen:
                passage = by_id[chunk]
                seen[chunk] = Citation(
                    chunk_id=chunk,
                    document_id=passage.document_id,
                    position=passage.position,
                    heading_path=passage.heading_path,
                    quote=quote_for(passage, claim.text),
                )
    return list(seen.values())


def render_answer(claims: list[ModelClaim], citations: list[Citation]) -> str:
    """Every sentence followed by the numbers of the citations it rests on: `text [1][3]`."""
    numbers = {citation.chunk_id: index for index, citation in enumerate(citations, start=1)}
    sentences = []
    for claim in claims:
        marks = "".join(f"[{numbers[c]}]" for c in dict.fromkeys(claim.chunk_ids) if c in numbers)
        sentences.append(f"{claim.text.strip()} {marks}".strip())
    return " ".join(sentences)


def confidence(output: AskOutput, retrieved: Retrieved) -> float:
    """Score deterministically: strong passages cited, more than a single claim."""
    score = 1.0
    cited = {c for claim in output.claims for c in claim.chunk_ids}
    strongest = max((p.score for p in retrieved.passages if p.chunk_id in cited), default=0.0)
    if strongest < STRONG_SCORE:
        score -= PENALTY_WEAK_PASSAGES
    if len(output.claims) <= 1:
        score -= PENALTY_FEW_CLAIMS
    return round(max(0.0, score), 2)


def not_found_response(
    retrieved: Retrieved, request_id: str, usage: Usage | None = None
) -> AskResponse:
    """Nothing worth reading came back: say so, cite nothing, charge what was spent."""
    return AskResponse(
        capability_version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        model=f"{descriptor.alias}@{retrieved.model_id}",
        eval_set_version=descriptor.eval_set_version,
        usage=usage or retrieved.usage,
        request_id=request_id,
        answer=NOT_FOUND_TEXT,
        citations=[],
        not_found=True,
        confidence=1.0,
    )


def to_response(
    output: AskOutput,
    result: GenerateResult,
    retrieved: Retrieved,
    request: AskRequest,
    request_id: str,
) -> AskResponse:
    """Check every claim, build the citations, log the row, build the response."""
    log_provider_call(_row(result, request, request_id))
    claims = [claim for claim in output.claims if claim.text.strip()]
    if output.not_found or not claims:
        return not_found_response(retrieved, request_id, result.usage)
    check_claims(output, retrieved.passages)
    citations = citations_of(output, retrieved.passages)
    return AskResponse(
        capability_version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        model=f"{descriptor.alias}@{result.model_id}",
        eval_set_version=descriptor.eval_set_version,
        usage=result.usage,
        request_id=request_id,
        answer=render_answer(claims, citations),
        citations=citations,
        not_found=False,
        confidence=confidence(output, retrieved),
    )


def _row(result: GenerateResult, request: AskRequest, request_id: str) -> ProviderCallRow:
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


def from_cache(text: str, request_id: str) -> AskResponse:
    """Rebuild a cached response under the new request id, marked as a hit and free."""
    cached = AskResponse.model_validate_json(text)
    usage = cached.usage.model_copy(update={"cache_hit": True, "cost_micros": 0, "latency_ms": 0})
    return cached.model_copy(update={"request_id": request_id, "usage": usage})
