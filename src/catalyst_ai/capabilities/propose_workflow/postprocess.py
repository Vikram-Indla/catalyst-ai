"""Stages 6 and 7: the structural check, the confidence, the response."""

from typing import Final

from catalyst_ai.capabilities.propose_workflow import descriptor
from catalyst_ai.capabilities.propose_workflow.schema import ModelOutput
from catalyst_ai.capabilities.propose_workflow.scheme import check_scheme
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.propose_workflow import (
    ProposeWorkflowRequest,
    ProposeWorkflowResponse,
    Status,
    Transition,
)
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.observability import ProviderCallRow, log_provider_call
from catalyst_ai.providers.port import GenerateResult

TOO_VAGUE: Final = "description_too_vague"
LARGE_SCHEME = 12
PENALTY_LARGE = 0.1
PENALTY_DEAD_END = 0.1
PENALTY_NO_PROGRESS = 0.1


def dead_ends(statuses: list[Status], transitions: list[Transition]) -> list[str]:
    """Statuses that are not terminal yet have no way out; a smell, not a refusal."""
    leaving = {t.from_key for t in transitions}
    if None in leaving:
        return []
    return sorted(s.key for s in statuses if not s.terminal and s.key not in leaving)


def confidence(statuses: list[Status], transitions: list[Transition]) -> float:
    """Score deterministically: size, dead ends, and whether work can be in progress at all."""
    score = 1.0
    if len(statuses) > LARGE_SCHEME:
        score -= PENALTY_LARGE
    if dead_ends(statuses, transitions):
        score -= PENALTY_DEAD_END
    if not any(s.category.value == "in_progress" for s in statuses):
        score -= PENALTY_NO_PROGRESS
    return round(max(0.0, score), 2)


def check_structure(output: ModelOutput, request: ProposeWorkflowRequest) -> None:
    """Refuse a proposal the backend's engine could not accept; every problem is a detail."""
    details = check_scheme(output.statuses, output.transitions, request)
    if details:
        raise Error(
            ErrorCode.OUTPUT_INVALID, "the proposed scheme is not well formed", details=details
        )


def to_response(
    output: ModelOutput, result: GenerateResult, request: ProposeWorkflowRequest, request_id: str
) -> ProposeWorkflowResponse:
    """Build the response: an empty proposal carries its reason; a full one passed the check."""
    empty = output.empty_reason is not None or not output.statuses
    if not empty:
        check_structure(output, request)
    log_provider_call(_row(result, request, request_id))
    return ProposeWorkflowResponse(
        capability_version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        model=f"{descriptor.alias}@{result.model_id}",
        eval_set_version=descriptor.eval_set_version,
        usage=result.usage,
        request_id=request_id,
        statuses=[] if empty else output.statuses,
        transitions=[] if empty else output.transitions,
        empty_reason=TOO_VAGUE if empty else None,
        confidence=1.0 if empty else confidence(output.statuses, output.transitions),
    )


def _row(
    result: GenerateResult, request: ProposeWorkflowRequest, request_id: str
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


def from_cache(text: str, request_id: str) -> ProposeWorkflowResponse:
    """Rebuild a cached response under the new request id, marked as a hit and free."""
    cached = ProposeWorkflowResponse.model_validate_json(text)
    usage = cached.usage.model_copy(update={"cache_hit": True, "cost_micros": 0, "latency_ms": 0})
    return cached.model_copy(update={"request_id": request_id, "usage": usage})
