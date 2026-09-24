"""Stages 6 and 7: the hierarchy check, sibling de-duplication, bounding, confidence, response."""

from catalyst_ai.capabilities.generate_children import descriptor
from catalyst_ai.capabilities.generate_children.drafts import as_drafts
from catalyst_ai.capabilities.generate_children.schema import ModelCandidate, ModelOutput
from catalyst_ai.contract.errors import ErrorCode, ErrorDetail
from catalyst_ai.contract.generate_children import (
    Candidate,
    GenerateChildrenRequest,
    GenerateChildrenResponse,
)
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.observability import ProviderCallRow, log_provider_call
from catalyst_ai.platform.similarity import nearest, similarity
from catalyst_ai.providers.port import GenerateResult

DUPLICATE_THRESHOLD = 0.6
HIERARCHY_VIOLATION = "hierarchy_violation"
STORY_LIKE = frozenset({"story", "user story", "feature"})
PENALTY_NO_CRITERIA = 0.2
PENALTY_DUPLICATE_SHARE = 0.3
MIN_CANDIDATE_DESCRIPTION = 1


def next_level(request: GenerateChildrenRequest) -> str | None:
    """Return the level right under the parent in the hierarchy; None when the parent is last."""
    levels = [level.lower() for level in request.hierarchy]
    if request.parent_level.lower() not in levels:
        return None
    index = levels.index(request.parent_level.lower())
    return request.hierarchy[index + 1] if index + 1 < len(levels) else None


def expected_child_level(request: GenerateChildrenRequest) -> str:
    """Return the level the candidates must carry: the parent's next; another request is refused."""
    below = next_level(request)
    if below is None:
        detail = ErrorDetail(
            field="parent_level",
            code=HIERARCHY_VIOLATION,
            message="not in the hierarchy or its last level",
        )
        raise Error(
            ErrorCode.INPUT_REJECTED, "the parent level has no level below it", details=[detail]
        )
    if request.child_level and request.child_level.lower() != below.lower():
        detail = ErrorDetail(
            field="child_level",
            code=HIERARCHY_VIOLATION,
            message=f"must be {below!r}, the level under the parent",
        )
        raise Error(
            ErrorCode.INPUT_REJECTED,
            "the child level is not the level under the parent",
            details=[detail],
        )
    return below


def check_hierarchy(output: ModelOutput, request: GenerateChildrenRequest) -> None:
    """Every candidate is exactly the expected child level; a single miss refuses the response."""
    expected = expected_child_level(request).lower()
    wrong = [c.title for c in output.candidates if c.type.lower() != expected]
    if wrong:
        details = [
            ErrorDetail(
                field="candidates",
                code=HIERARCHY_VIOLATION,
                message=f"{len(wrong)} candidate(s) not at level {expected!r}",
            )
        ]
        raise Error(
            ErrorCode.OUTPUT_INVALID, "a candidate is not at the child level", details=details
        )


def mark_duplicates(candidates: list[ModelCandidate], siblings: list[str]) -> list[ModelCandidate]:
    """Set `duplicate_of` on every candidate that repeats a sibling or an earlier candidate."""
    marked: list[ModelCandidate] = []
    for candidate in candidates:
        sibling = candidate.duplicate_of or nearest(candidate.title, siblings, DUPLICATE_THRESHOLD)
        earlier = nearest(
            candidate.title,
            [m.title for m in marked if m.duplicate_of is None],
            DUPLICATE_THRESHOLD,
        )
        marked.append(candidate.model_copy(update={"duplicate_of": sibling or earlier}))
    return marked


def bound(candidates: list[ModelCandidate], max_items: int) -> list[ModelCandidate]:
    """At most `max_items` new candidates; duplicates ride along without counting."""
    kept: list[ModelCandidate] = []
    new = 0
    for candidate in candidates:
        if candidate.duplicate_of is None:
            if new >= max_items:
                continue
            new += 1
        kept.append(candidate)
    return kept


def candidate_confidence(
    candidate: ModelCandidate, request: GenerateChildrenRequest, level: str
) -> float:
    """Score deterministically: criteria where story-like, not a near duplicate, grounded."""
    score = 1.0
    if level.lower() in STORY_LIKE and not candidate.acceptance_criteria:
        score -= PENALTY_NO_CRITERIA
    if candidate.duplicate_of is not None:
        score -= PENALTY_DUPLICATE_SHARE
    grounding = (
        request.parent_title
        + "\n"
        + request.parent_description
        + "\n"
        + "\n".join(request.source_texts)
    )
    if similarity(candidate.title + " " + candidate.description, grounding) == 0.0:
        score -= PENALTY_DUPLICATE_SHARE
    return round(max(0.0, score), 2)


def to_response(
    output: ModelOutput,
    result: GenerateResult,
    request: GenerateChildrenRequest,
    request_id: str,
    indexed: tuple[str, ...] | None = None,
) -> GenerateChildrenResponse:
    """Validate the hierarchy, mark duplicates, bound, score, log the row, build the response."""
    check_hierarchy(output, request)
    level = expected_child_level(request)
    pool = [s.title for s in request.siblings] + [t for t in indexed or () if t]
    drafts, withheld = as_drafts(output.candidates, request)
    marked = bound(mark_duplicates(drafts, pool), request.max_items)
    candidates = [
        Candidate(
            type=c.type,
            title=c.title,
            description=c.description,
            acceptance_criteria=c.acceptance_criteria,
            confidence=candidate_confidence(c, request, level),
            duplicate_of=c.duplicate_of,
            draft=request.draft_only,
        )
        for c in marked
    ]
    log_provider_call(_row(result, request, request_id))
    new_ones = [c.confidence for c in candidates if c.duplicate_of is None]
    return GenerateChildrenResponse(
        capability_version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        model=f"{descriptor.alias}@{result.model_id}",
        eval_set_version=descriptor.eval_set_version,
        usage=result.usage,
        request_id=request_id,
        candidates=candidates,
        empty_reason=output.empty_reason if not new_ones else None,
        confidence=round(sum(new_ones) / len(new_ones), 2) if new_ones else None,
        index_consulted=indexed is not None,
        withheld=withheld,
    )


def _row(
    result: GenerateResult, request: GenerateChildrenRequest, request_id: str
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


def from_cache(text: str, request_id: str) -> GenerateChildrenResponse:
    """Rebuild a cached response under the new request id, marked as a hit and free."""
    cached = GenerateChildrenResponse.model_validate_json(text)
    usage = cached.usage.model_copy(update={"cache_hit": True, "cost_micros": 0, "latency_ms": 0})
    return cached.model_copy(update={"request_id": request_id, "usage": usage})
