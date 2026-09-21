"""Stage 7: the card, with only the facts the supplied text carries; the row; the cache."""

import re

from catalyst_ai.capabilities.unfurl import descriptor
from catalyst_ai.capabilities.unfurl.schema import ModelOutput
from catalyst_ai.contract.unfurl import Fact, UnfurlRequest, UnfurlResponse
from catalyst_ai.platform.observability import ProviderCallRow, log_provider_call
from catalyst_ai.providers.port import GenerateResult

WORD = re.compile(r"[\w#/.:-]{3,}", re.UNICODE)
PENALTY_DROPPED = 0.15
PENALTY_NO_TEXT = 0.1


def _words(text: str) -> set[str]:
    return {w.lower().strip(".,;:") for w in WORD.findall(text)} - {""}


def carried(value: str, request: UnfurlRequest) -> bool:
    """Whether every word of the value appears in the title, the status or the text."""
    haystack = _words(" ".join([request.title, request.status or "", request.text or ""]))
    return all(word in haystack for word in _words(value))


def kept_facts(output: ModelOutput, request: UnfurlRequest) -> list[Fact]:
    """Facts whose value the supplied text carries; the rest are dropped, never returned."""
    return [
        Fact(label=f.label.strip(), value=f.value.strip())
        for f in output.facts
        if carried(f.value, request)
    ]


def confidence(output: ModelOutput, facts: list[Fact], request: UnfurlRequest) -> float:
    """Score deterministically: every fact kept; a text to draw on."""
    score = 1.0
    if len(facts) < len(output.facts):
        score -= PENALTY_DROPPED
    if not request.text:
        score -= PENALTY_NO_TEXT
    return round(max(0.0, score), 2)


def to_response(
    output: ModelOutput, result: GenerateResult, request: UnfurlRequest, request_id: str
) -> UnfurlResponse:
    """Lay the card out; log the content-free row."""
    log_provider_call(_row(result, request, request_id))
    facts = kept_facts(output, request)
    return UnfurlResponse(
        capability_version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        model=f"{descriptor.alias}@{result.model_id}",
        eval_set_version=descriptor.eval_set_version,
        usage=result.usage,
        request_id=request_id,
        title=request.title,
        summary=output.summary.strip(),
        facts=facts,
        confidence=confidence(output, facts, request),
    )


def _row(result: GenerateResult, request: UnfurlRequest, request_id: str) -> ProviderCallRow:
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


def from_cache(text: str, request_id: str) -> UnfurlResponse:
    """Rebuild a cached response under the new request id, marked as a hit and free."""
    cached = UnfurlResponse.model_validate_json(text)
    usage = cached.usage.model_copy(update={"cache_hit": True, "cost_micros": 0, "latency_ms": 0})
    return cached.model_copy(update={"request_id": request_id, "usage": usage})
