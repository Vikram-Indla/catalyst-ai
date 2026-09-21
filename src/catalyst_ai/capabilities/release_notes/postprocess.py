"""Stages 6 and 7: traceability, tokens, the sections in the changes' order, the response."""

from typing import Final

from catalyst_ai.capabilities.release_notes import descriptor
from catalyst_ai.capabilities.release_notes.schema import ModelEntry, ModelOutput
from catalyst_ai.contract.release_notes import (
    Entry,
    ReleaseNotesRequest,
    ReleaseNotesResponse,
    Section,
    StatusCategory,
)
from catalyst_ai.platform.language.records import refuse_foreign_tokens, refuse_untraceable
from catalyst_ai.platform.observability import ProviderCallRow, log_provider_call
from catalyst_ai.providers.port import GenerateResult

NOTHING: Final = "nothing_to_report"
PENALTY_UNCOVERED = 0.2
PENALTY_NO_HIGHLIGHT = 0.1


def cited(output: ModelOutput) -> list[tuple[str, str]]:
    """Every (field, source id) pair the completion cites."""
    pairs = [(f"sections.{s.kind}", e.source_id) for s in output.sections for e in s.entries]
    pairs += [("highlights", e.source_id) for e in output.highlights]
    return pairs + [("attention", e.source_id) for e in output.attention]


def check_records(output: ModelOutput, request: ReleaseNotesRequest) -> None:
    """Every entry cites a change the request carried; no token the changes did not."""
    refuse_untraceable(cited(output), {c.id for c in request.changes})
    known = {c.participant for c in request.changes if c.participant}
    text = "\n".join(
        [output.summary]
        + [e.text for s in output.sections for e in s.entries]
        + [e.text for e in output.highlights + output.attention]
    )
    refuse_foreign_tokens(text, [], known, "summary")


def _entries(entries: list[ModelEntry]) -> list[Entry]:
    return [Entry(source_id=e.source_id, text=e.text.strip()) for e in entries if e.text.strip()]


def sections_of(output: ModelOutput, request: ReleaseNotesRequest) -> list[Section]:
    """One section per kind in the order the changes came; entries in the changes' order."""
    by_source = {e.source_id: e for s in output.sections for e in s.entries}
    kinds: list[str] = []
    for change in request.changes:
        if change.kind not in kinds:
            kinds.append(change.kind)
    sections = [
        Section(
            kind=kind,
            entries=_entries(
                [by_source[c.id] for c in request.changes if c.kind == kind and c.id in by_source]
            ),
        )
        for kind in kinds
    ]
    return [section for section in sections if section.entries]


def in_flight(request: ReleaseNotesRequest) -> list[str]:
    """Return the ids of the changes not yet done — listed, never counted."""
    return [c.id for c in request.changes if c.status_category is not StatusCategory.DONE]


def confidence(
    sections: list[Section], highlights: list[Entry], request: ReleaseNotesRequest
) -> float:
    """Score deterministically: every done change noted, a highlight present in notes mode."""
    score = 1.0
    if request.mode.value == "notes":
        noted = {e.source_id for s in sections for e in s.entries}
        done = {c.id for c in request.changes if c.status_category is StatusCategory.DONE}
        if done - noted:
            score -= PENALTY_UNCOVERED
        if not highlights:
            score -= PENALTY_NO_HIGHLIGHT
    return round(max(0.0, score), 2)


def to_response(
    output: ModelOutput, result: GenerateResult, request: ReleaseNotesRequest, request_id: str
) -> ReleaseNotesResponse:
    """Check the records, lay the sections out, log the row, build the response."""
    empty = output.empty_reason is not None or not request.changes
    if not empty:
        check_records(output, request)
    sections = sections_of(output, request) if not empty else []
    highlights = _entries(output.highlights) if not empty else []
    log_provider_call(_row(result, request, request_id))
    return ReleaseNotesResponse(
        capability_version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        model=f"{descriptor.alias}@{result.model_id}",
        eval_set_version=descriptor.eval_set_version,
        usage=result.usage,
        request_id=request_id,
        sections=sections,
        highlights=highlights,
        summary="" if empty else output.summary.strip(),
        attention=_entries(output.attention) if not empty else [],
        in_flight=in_flight(request),
        empty_reason=NOTHING if empty else None,
        confidence=1.0 if empty else confidence(sections, highlights, request),
    )


def _row(result: GenerateResult, request: ReleaseNotesRequest, request_id: str) -> ProviderCallRow:
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


def from_cache(text: str, request_id: str) -> ReleaseNotesResponse:
    """Rebuild a cached response under the new request id, marked as a hit and free."""
    cached = ReleaseNotesResponse.model_validate_json(text)
    usage = cached.usage.model_copy(update={"cache_hit": True, "cost_micros": 0, "latency_ms": 0})
    return cached.model_copy(update={"request_id": request_id, "usage": usage})
