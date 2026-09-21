"""Stage 7: the validated translation becomes the response with the languages and a confidence."""

from catalyst_ai.capabilities.translate import descriptor
from catalyst_ai.capabilities.translate.quality import (
    in_target_script,
    kept_spans,
    skeleton,
    structure_preserved,
)
from catalyst_ai.capabilities.translate.schema import ModelOutput
from catalyst_ai.contract.translate import TranslateMode, TranslateRequest, TranslateResponse
from catalyst_ai.platform.language import length_ratio
from catalyst_ai.platform.observability import ProviderCallRow, log_provider_call
from catalyst_ai.providers.port import GenerateResult

MIN_RATIO = 0.3
MAX_RATIO = 3.0
PENALTY_SCRIPT = 0.4
PENALTY_STRUCTURE = 0.2
PENALTY_SPANS = 0.3
PENALTY_LENGTH = 0.1


def confidence(request: TranslateRequest, translated: str, target: str) -> float:
    """Score deterministically: the target script, the structure, the kept spans, the length."""
    score = 1.0
    if not in_target_script(translated, target):
        score -= PENALTY_SCRIPT
    if request.mode is TranslateMode.FIELD and skeleton(request.text) != skeleton(translated):
        score -= PENALTY_STRUCTURE
    if not set(kept_spans(request.text)) <= set(kept_spans(translated)):
        score -= PENALTY_SPANS
    if not MIN_RATIO <= length_ratio(request.text, translated) <= MAX_RATIO:
        score -= PENALTY_LENGTH
    return round(max(0.0, score), 2)


def to_response(
    output: ModelOutput,
    result: GenerateResult,
    request: TranslateRequest,
    request_id: str,
    detected: str,
) -> TranslateResponse:
    """Log the content-free row and build the response; a title is one line."""
    target = request.target_language or ""
    translated = output.translated_text.strip()
    if request.mode is TranslateMode.TITLE:
        translated = " ".join(translated.split())
    log_provider_call(_row(result, request, request_id))
    return TranslateResponse(
        capability_version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        model=f"{descriptor.alias}@{result.model_id}",
        eval_set_version=descriptor.eval_set_version,
        usage=result.usage,
        request_id=request_id,
        translated_text=translated,
        detected_language=detected,
        target_language=target,
        structure_preserved=request.mode is TranslateMode.TITLE
        or structure_preserved(request.text, translated),
        confidence=confidence(request, translated, target),
    )


def _row(result: GenerateResult, request: TranslateRequest, request_id: str) -> ProviderCallRow:
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


def from_cache(text: str, request_id: str) -> TranslateResponse:
    """Rebuild a cached response under the new request id, marked as a hit and free."""
    cached = TranslateResponse.model_validate_json(text)
    usage = cached.usage.model_copy(update={"cache_hit": True, "cost_micros": 0, "latency_ms": 0})
    return cached.model_copy(update={"request_id": request_id, "usage": usage})
