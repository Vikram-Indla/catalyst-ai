"""The generate pipeline: a draft from supplied sources, every section citing what it rests on."""

from dataclasses import dataclass
from pathlib import Path
from typing import Final

from catalyst_ai.capabilities.documents import descriptor
from catalyst_ai.capabilities.documents.citations import UNCITED
from catalyst_ai.capabilities.documents.schema import DraftOutput, draft_prose, draft_schema
from catalyst_ai.contract.documents import DraftRequest, DraftResponse, DraftSection, Source
from catalyst_ai.contract.errors import ErrorCode, ErrorDetail
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.language.records import refuse_untraceable
from catalyst_ai.platform.observability import ProviderCallRow, log_provider_call
from catalyst_ai.platform.pipeline import Door, Stages, admit, parse_with_repair, run_stages
from catalyst_ai.platform.prompts import PromptFile, fill
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.platform.safety import fence, refuse_if_unsafe
from catalyst_ai.providers.port import GenerateRequest, GenerateResult, ModelAlias, Segment

PROMPT_PATH = Path(__file__).with_name(f"prompt_v{descriptor.prompt_version}.md")
ABSENT = "(none)"
PRESERVE = "the brief's own"
INSUFFICIENT: Final = "sources_insufficient"
PENALTY_UNUSED_SOURCES = 0.1
PENALTY_LENGTH = 0.2
CAP_SHARE = 1.5


@dataclass(frozen=True)
class Parsed:
    """The request plus the texts the door scans and the prompt fences."""

    request: DraftRequest
    request_id: str
    idempotency: str | None
    user_texts: dict[str, str | None]


def source_text(source: Source) -> str:
    """One source as the prompt reads it: its id, its title, its text."""
    title = f" {source.title}" if source.title else ""
    return f"[{source.id}]{title}\n{source.text}"


def parse(request: DraftRequest, request_id: str, idempotency: str | None) -> Parsed:
    """Stage 1: the typed request becomes the pipeline's input; the sources become one text."""
    texts: dict[str, str | None] = {
        "brief": request.brief,
        "sources": "\n\n".join(source_text(s) for s in request.sources),
    }
    return Parsed(request, request_id, idempotency, texts)


def validate(parsed: Parsed, runtime: RuntimeContext) -> str:
    """Stage 2: the door — switch, version, scanner, tenant cap; return the cache key."""
    door = Door(
        name=descriptor.name,
        version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        alias=descriptor.alias,
        settings=runtime.settings.capability_documents,
        organization_id=parsed.request.organization_id,
        capability_version=parsed.request.capability_version,
        user_texts=parsed.user_texts,
        canonical_input=parsed.request.model_dump(mode="json"),
        idempotency=parsed.idempotency,
    )
    return admit(door, runtime)


def assemble(parsed: Parsed, runtime: RuntimeContext) -> GenerateRequest:
    """Stage 4: the prompt file, filled; the brief and the sources fenced as data."""
    request = parsed.request
    prompt = PromptFile.load(PROMPT_PATH)
    developer = fill(
        prompt.section("developer"),
        {
            "language": request.language or PRESERVE,
            "instructions": fill(
                prompt.section("mode:generate"),
                {
                    "target_words": str(request.target_words),
                    "max_words": str(int(request.target_words * CAP_SHARE)),
                },
            ),
        },
    )
    segments = [
        Segment(role="system", name="system", text=prompt.section("system")),
        Segment(role="developer", name="developer", text=developer),
        Segment(role="user", name="question", text=fence("question", request.brief)),
        Segment(
            role="user",
            name="passages",
            text=fence("passages", parsed.user_texts["sources"] or ABSENT),
        ),
    ]
    timeout = runtime.settings.capability_documents.timeout_ms or descriptor.timeout_ms
    return GenerateRequest(
        organization_id=request.organization_id,
        request_id=parsed.request_id,
        capability=descriptor.name,
        alias=ModelAlias(descriptor.alias),
        segments=segments,
        output_schema=draft_schema(),
        temperature=descriptor.temperature,
        max_output_tokens=descriptor.max_output_tokens,
        timeout_ms=timeout,
    )


async def call(generate: GenerateRequest, runtime: RuntimeContext) -> GenerateResult:
    """Stage 5: the one provider call, inside the tenant's concurrency slot."""
    async with runtime.budgets.slot(generate.organization_id):
        return await runtime.provider.generate(generate)


async def validate_output(
    result: GenerateResult, generate: GenerateRequest, parsed: Parsed, runtime: RuntimeContext
) -> tuple[DraftOutput, GenerateResult]:
    """Stage 6: parse against the schema with one repair attempt; then the leakage scan."""
    output, current = await parse_with_repair(result, DraftOutput, lambda: call(generate, runtime))
    texts = [text for text in parsed.user_texts.values() if text]
    refuse_if_unsafe(draft_prose(output), texts, parsed.request_id)
    return output, current


def sections_of(output: DraftOutput, request: DraftRequest) -> list[DraftSection]:
    """Return the sections with text, each checked against the source ids the request carried."""
    kept = [s for s in output.sections if s.heading.strip() and s.text.strip()]
    cited = [(f"sections.{i}", source) for i, s in enumerate(kept) for source in s.sources]
    refuse_untraceable(cited, {source.id for source in request.sources})
    uncited = [
        ErrorDetail(field=f"sections.{i}", code=UNCITED, message="no source behind the section")
        for i, s in enumerate(kept)
        if not s.sources
    ]
    if uncited:
        raise Error(ErrorCode.OUTPUT_INVALID, "a section cites nothing", details=uncited)
    return [
        DraftSection(
            heading=s.heading.strip(), text=s.text.strip(), sources=list(dict.fromkeys(s.sources))
        )
        for s in kept
    ]


def confidence(sections: list[DraftSection], request: DraftRequest) -> float:
    """Score deterministically: every source used, the length near the target."""
    score = 1.0
    used = {source for section in sections for source in section.sources}
    if {source.id for source in request.sources} - used:
        score -= PENALTY_UNUSED_SOURCES
    words = sum(len(section.text.split()) for section in sections)
    if words > request.target_words * CAP_SHARE:
        score -= PENALTY_LENGTH
    return round(max(0.0, score), 2)


def postprocess(
    output: DraftOutput, result: GenerateResult, parsed: Parsed, runtime: RuntimeContext
) -> DraftResponse:
    """Stage 7: settle the spend; traceability of every section; the response."""
    runtime.budgets.settle(parsed.request.organization_id, result.usage.cost_micros)
    log_provider_call(_row(result, parsed.request, parsed.request_id))
    empty = output.empty_reason is not None or not output.sections
    sections = sections_of(output, parsed.request) if not empty else []
    return DraftResponse(
        capability_version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        model=f"{descriptor.alias}@{result.model_id}",
        eval_set_version=descriptor.eval_set_version,
        usage=result.usage,
        request_id=parsed.request_id,
        title="" if empty else output.title.strip(),
        sections=sections,
        empty_reason=INSUFFICIENT if empty else None,
        confidence=1.0 if empty else confidence(sections, parsed.request),
    )


def _row(result: GenerateResult, request: DraftRequest, request_id: str) -> ProviderCallRow:
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


def from_cache(text: str, request_id: str) -> DraftResponse:
    """Rebuild a cached response under the new request id, marked as a hit and free."""
    cached = DraftResponse.model_validate_json(text)
    usage = cached.usage.model_copy(update={"cache_hit": True, "cost_micros": 0, "latency_ms": 0})
    return cached.model_copy(update={"request_id": request_id, "usage": usage})


def _cache_ttl(runtime: RuntimeContext) -> int:
    ttl = runtime.settings.capability_documents.cache_ttl_seconds
    return descriptor.cache_ttl_seconds if ttl is None else ttl


STAGES = Stages(
    parse=parse,
    validate=validate,
    retrieve=None,
    assemble=assemble,
    call=call,
    validate_output=validate_output,
    postprocess=postprocess,
    from_cache=from_cache,
    cache_ttl=_cache_ttl,
)


async def run(
    request: DraftRequest, runtime: RuntimeContext, request_id: str, idempotency: str | None = None
) -> DraftResponse:
    """Run the stages in order, with the cache in front of the call."""
    return await run_stages(STAGES, request, runtime, request_id, idempotency)
