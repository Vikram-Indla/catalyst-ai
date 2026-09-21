"""Stages 6 and 7: traceability of cases and tables, the bounds, the gaps, the response."""

from typing import Final

from catalyst_ai.capabilities.generate_tests import descriptor
from catalyst_ai.capabilities.generate_tests.schema import ModelOutput
from catalyst_ai.contract.errors import ErrorCode, ErrorDetail
from catalyst_ai.contract.generate_tests import (
    DataTable,
    GenerateTestsRequest,
    GenerateTestsResponse,
    OutlineSection,
    TestCase,
)
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.language.records import UNTRACEABLE, refuse_untraceable
from catalyst_ai.platform.observability import ProviderCallRow, log_provider_call
from catalyst_ai.providers.port import GenerateResult

NOTHING: Final = "nothing_to_test"
PENALTY_GAPS = 0.2
PENALTY_INFERRED = 0.1
PENALTY_ONE_AREA = 0.1


def cited(output: ModelOutput) -> list[tuple[str, str]]:
    """Every (field, source id) pair the completion cites."""
    pairs = [(f"cases.{i}", c) for i, case in enumerate(output.cases) for c in case.covers]
    pairs += [(f"outline.{i}", c) for i, s in enumerate(output.outline) for c in s.covers]
    return pairs + [
        (f"data_tables.{i}", c) for i, t in enumerate(output.data_tables) for c in t.covers
    ]


def check_records(output: ModelOutput, request: GenerateTestsRequest) -> None:
    """Every citation names a criterion or a case the request carried; a stated case cites one."""
    sources = {c.id for c in request.criteria} | {c.id for c in request.cases}
    refuse_untraceable(cited(output), sources)
    uncited = [
        ErrorDetail(field=f"cases.{i}", code=UNTRACEABLE, message="no criterion and not inferred")
        for i, case in enumerate(output.cases)
        if not case.covers and not case.inferred
    ]
    if uncited:
        raise Error(ErrorCode.OUTPUT_INVALID, "a case cites nothing", details=uncited)


def cases_of(output: ModelOutput, request: GenerateTestsRequest) -> list[TestCase]:
    """Return the cases, at most `max_cases`, in the model's order."""
    return [
        TestCase(
            title=c.title.strip(),
            given=c.given.strip(),
            when=c.when.strip(),
            then=c.then.strip(),
            priority=c.priority,
            area=c.area,
            covers=list(dict.fromkeys(c.covers)),
            inferred=c.inferred,
        )
        for c in output.cases[: request.max_cases]
        if c.title.strip() and c.given.strip() and c.when.strip() and c.then.strip()
    ]


def gaps_of(cases: list[TestCase], request: GenerateTestsRequest) -> list[str]:
    """Return the criteria no kept case covers, in the request's order — never the model's."""
    covered = {c for case in cases for c in case.covers}
    return [c.id for c in request.criteria if c.id not in covered]


def artefacts_of(output: ModelOutput) -> tuple[list[OutlineSection], list[DataTable]]:
    """Return the outline and the tables, cleaned; a table without a column or citation goes."""
    outline = [
        OutlineSection(
            heading=s.heading.strip(), lines=[x for x in s.lines if x.strip()], covers=s.covers
        )
        for s in output.outline
        if s.heading.strip()
    ]
    tables = [
        DataTable(name=t.name.strip(), columns=t.columns, rows=t.rows, covers=t.covers)
        for t in output.data_tables
        if t.name.strip() and t.columns and t.covers
    ]
    return outline, tables


def confidence(cases: list[TestCase], gaps: list[str], request: GenerateTestsRequest) -> float:
    """Score deterministically: gaps left, inferred cases, a single coverage area."""
    score = 1.0
    if request.mode.value == "cases":
        if gaps:
            score -= PENALTY_GAPS
        if any(c.inferred for c in cases):
            score -= PENALTY_INFERRED
        if len({c.area for c in cases}) <= 1 and len(cases) > 1:
            score -= PENALTY_ONE_AREA
    return round(max(0.0, score), 2)


def to_response(
    output: ModelOutput, result: GenerateResult, request: GenerateTestsRequest, request_id: str
) -> GenerateTestsResponse:
    """Check the records, bound the cases, compute the gaps, log the row, build the response."""
    empty = output.empty_reason is not None
    if not empty:
        check_records(output, request)
    cases = cases_of(output, request) if not empty and request.mode.value == "cases" else []
    outline, tables = (
        artefacts_of(output) if not empty and request.mode.value != "cases" else ([], [])
    )
    gaps = gaps_of(cases, request) if request.mode.value == "cases" and not empty else []
    log_provider_call(_row(result, request, request_id))
    return GenerateTestsResponse(
        capability_version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        model=f"{descriptor.alias}@{result.model_id}",
        eval_set_version=descriptor.eval_set_version,
        usage=result.usage,
        request_id=request_id,
        cases=cases,
        gaps=gaps,
        outline=outline,
        data_tables=tables,
        empty_reason=NOTHING if empty else None,
        confidence=1.0 if empty else confidence(cases, gaps, request),
    )


def _row(result: GenerateResult, request: GenerateTestsRequest, request_id: str) -> ProviderCallRow:
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


def from_cache(text: str, request_id: str) -> GenerateTestsResponse:
    """Rebuild a cached response under the new request id, marked as a hit and free."""
    cached = GenerateTestsResponse.model_validate_json(text)
    usage = cached.usage.model_copy(update={"cache_hit": True, "cost_micros": 0, "latency_ms": 0})
    return cached.model_copy(update={"request_id": request_id, "usage": usage})
