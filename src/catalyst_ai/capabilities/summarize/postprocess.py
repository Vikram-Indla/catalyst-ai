"""Stages 6 and 7: the participant rule, the length cap, the covered range, the response."""

import re

from catalyst_ai.capabilities.summarize import descriptor
from catalyst_ai.capabilities.summarize.schema import ModelOutput
from catalyst_ai.contract.errors import ErrorCode, ErrorDetail
from catalyst_ai.contract.summarize import CoveredRange, SummarizeRequest, SummarizeResponse
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.observability import ProviderCallRow, log_provider_call
from catalyst_ai.providers.port import GenerateResult

TOKEN = re.compile(r"\bp[0-9]{1,4}\b")
WORD = re.compile(r"\S+")
HEADING = re.compile(r"^\s{0,3}#{1,6}\s", re.M)
FENCE = "```"
CAP_SHARE = 1.5
PENALTY_LENGTH = 0.2
PENALTY_STRUCTURE = 0.2
PARTICIPANT_LEAK = "participant_not_in_thread"


def tokens_in(text: str) -> set[str]:
    """Every participant token a text names."""
    return set(TOKEN.findall(text))


def check_participants(summary: str, mentioned: list[str], request: SummarizeRequest) -> None:
    """Refuse a token outside the thread's: the summary named someone the data did not."""
    known = {item.participant for item in request.items} | {
        change.participant for change in request.status_changes
    }
    foreign = (tokens_in(summary) | set(mentioned)) - known
    if foreign:
        detail = ErrorDetail(
            field="summary", code=PARTICIPANT_LEAK, message=f"{len(foreign)} unknown token(s)"
        )
        raise Error(
            ErrorCode.OUTPUT_UNSAFE,
            "the summary names a participant outside the thread",
            details=[detail],
        )


def word_count(text: str) -> int:
    """Words as whitespace-separated runs."""
    return len(WORD.findall(text))


def cap_words(text: str, limit: int) -> str:
    """Cut a summary at the word limit, at a line end where one falls inside the last tenth."""
    words = WORD.findall(text)
    if len(words) <= limit:
        return text
    kept = " ".join(words[:limit])
    return kept.rstrip(" ,;:-") + " …"


def strip_structure(text: str) -> str:
    """Headings and code fences are not allowed in a summary; the markers go, the words stay."""
    without_fences = text.replace(FENCE, "")
    return HEADING.sub("", without_fences)


def covered_range(request: SummarizeRequest) -> CoveredRange:
    """Return the first and last item ids the summary rests on."""
    if not request.items:
        return CoveredRange(first_id=None, last_id=None, count=0)
    return CoveredRange(
        first_id=request.items[0].id, last_id=request.items[-1].id, count=len(request.items)
    )


def confidence(summary: str, output: ModelOutput, request: SummarizeRequest) -> float:
    """Score deterministically: the length wanted, no structure stripped."""
    score = 1.0
    if word_count(summary) > request.target_words * CAP_SHARE:
        score -= PENALTY_LENGTH
    if HEADING.search(output.summary) or FENCE in output.summary:
        score -= PENALTY_STRUCTURE
    return round(max(0.0, score), 2)


def to_response(
    output: ModelOutput, result: GenerateResult, request: SummarizeRequest, request_id: str
) -> SummarizeResponse:
    """Check the participants, cap the length, strip structure, log the row, build the response."""
    check_participants(output.summary, output.participants_mentioned, request)
    summary = cap_words(
        strip_structure(output.summary).strip(), int(request.target_words * CAP_SHARE)
    )
    log_provider_call(_row(result, request, request_id))
    empty = not summary.strip() or output.empty_reason is not None
    return SummarizeResponse(
        capability_version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        model=f"{descriptor.alias}@{result.model_id}",
        eval_set_version=descriptor.eval_set_version,
        usage=result.usage,
        request_id=request_id,
        summary="" if empty else summary,
        empty_reason="nothing_to_summarize" if empty else None,
        covered_range=covered_range(request),
        participants_mentioned=sorted(tokens_in(summary)) if not empty else [],
        confidence=confidence(summary, output, request) if not empty else 1.0,
    )


def _row(result: GenerateResult, request: SummarizeRequest, request_id: str) -> ProviderCallRow:
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


def from_cache(text: str, request_id: str) -> SummarizeResponse:
    """Rebuild a cached response under the new request id, marked as a hit and free."""
    cached = SummarizeResponse.model_validate_json(text)
    usage = cached.usage.model_copy(update={"cache_hit": True, "cost_micros": 0, "latency_ms": 0})
    return cached.model_copy(update={"request_id": request_id, "usage": usage})
