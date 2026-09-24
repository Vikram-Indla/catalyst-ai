"""Stage 7: the validated output becomes the response model with provenance and confidence."""

from catalyst_ai.capabilities.improve_story import descriptor
from catalyst_ai.capabilities.improve_story.quality import (
    identifiers_preserved,
    length_ratio,
    script_preserved,
)
from catalyst_ai.capabilities.improve_story.schema import ModelOutput
from catalyst_ai.contract.improve_story import (
    COMMENT_MODES,
    ImproveStoryRequest,
    ImproveStoryResponse,
)
from catalyst_ai.platform.observability import ProviderCallRow, log_provider_call
from catalyst_ai.providers.port import GenerateResult

MIN_RATIO = 0.5
MAX_RATIO = 3.0
PENALTY_IDENTIFIERS = 0.3
PENALTY_LENGTH = 0.2
PENALTY_SCRIPT = 0.3


def source_text(request: ImproveStoryRequest) -> str:
    """Return the text the mode rewrites: the comment for a comment mode, else the description."""
    return request.comment.text if request.comment else request.description


def confidence(request: ImproveStoryRequest, output: ModelOutput) -> float:
    """Score deterministically: start at one, lose a fixed share per violated property."""
    score = 1.0
    source = source_text(request)
    if not identifiers_preserved(source, output.description):
        score -= PENALTY_IDENTIFIERS
    if output.changed and not MIN_RATIO <= length_ratio(source, output.description) <= MAX_RATIO:
        score -= PENALTY_LENGTH
    if request.language is None and not script_preserved(source, output.description):
        score -= PENALTY_SCRIPT
    return round(max(0.0, score), 2)


def to_response(
    output: ModelOutput, result: GenerateResult, request: ImproveStoryRequest, request_id: str
) -> ImproveStoryResponse:
    """Log the content-free row and build the response."""
    log_provider_call(
        ProviderCallRow(
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
    )
    return ImproveStoryResponse(
        capability_version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        model=f"{descriptor.alias}@{result.model_id}",
        eval_set_version=descriptor.eval_set_version,
        usage=result.usage,
        request_id=request_id,
        improved_description=output.description,
        acceptance_criteria=None if request.mode in COMMENT_MODES else output.acceptance_criteria,
        rationale=output.rationale,
        changed=output.changed,
        confidence=confidence(request, output),
    )


def from_cache(text: str, request_id: str) -> ImproveStoryResponse:
    """Rebuild a cached response under the new request id, marked as a hit and free."""
    cached = ImproveStoryResponse.model_validate_json(text)
    usage = cached.usage.model_copy(update={"cache_hit": True, "cost_micros": 0, "latency_ms": 0})
    return cached.model_copy(update={"request_id": request_id, "usage": usage})
