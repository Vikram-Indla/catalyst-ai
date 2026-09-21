"""The post-mortem pipeline: parse, validate, assemble, call, validate_output, postprocess."""

from dataclasses import dataclass
from pathlib import Path

from catalyst_ai.capabilities.post_mortem import descriptor
from catalyst_ai.capabilities.post_mortem.postprocess import from_cache, to_response
from catalyst_ai.capabilities.post_mortem.schema import ModelOutput, output_schema, prose_of
from catalyst_ai.contract.post_mortem import Event, PostMortemRequest, PostMortemResponse
from catalyst_ai.platform.pipeline import Door, Stages, admit, parse_with_repair, run_stages
from catalyst_ai.platform.prompts import PromptFile, fill
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.platform.safety import fence, refuse_if_unsafe
from catalyst_ai.providers.port import GenerateRequest, GenerateResult, ModelAlias, Segment

PROMPT_PATH = Path(__file__).with_name(f"prompt_v{descriptor.prompt_version}.md")
ABSENT = "(none)"
PRESERVE = "the timeline's own"


@dataclass(frozen=True)
class Parsed:
    """The request plus the texts the door scans and the prompt fences."""

    request: PostMortemRequest
    request_id: str
    idempotency: str | None
    user_texts: dict[str, str | None]


def _event_line(event: Event) -> str:
    who = f" {event.participant}" if event.participant else ""
    return f"[{event.id}]{who} @ {event.at.isoformat()}: {event.text}"


def timeline_text(request: PostMortemRequest) -> str:
    """One line per entry: the id every fact must cite, the token, the time, the text."""
    return "\n".join(_event_line(event) for event in request.timeline)


def incident_text(request: PostMortemRequest) -> str:
    """Return the incident's own facts, one per line."""
    incident = request.incident
    lines = [f"title: {incident.title}"]
    for label, value in (
        ("key", incident.key),
        ("severity", incident.severity),
        ("started", incident.started_at.isoformat() if incident.started_at else None),
        ("resolved", incident.resolved_at.isoformat() if incident.resolved_at else None),
        ("impact", incident.impact),
    ):
        if value:
            lines.append(f"{label}: {value}")
    return "\n".join(lines)


def parse(request: PostMortemRequest, request_id: str, idempotency: str | None) -> Parsed:
    """Stage 1: the typed request becomes the pipeline's input; the timeline becomes one text."""
    texts: dict[str, str | None] = {
        "timeline": timeline_text(request) or None,
        "incident": incident_text(request),
    }
    return Parsed(request, request_id, idempotency, texts)


def validate(parsed: Parsed, runtime: RuntimeContext) -> str:
    """Stage 2: the door — switch, version, scanner, tenant cap; return the cache key."""
    door = Door(
        name=descriptor.name,
        version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        alias=descriptor.alias,
        settings=runtime.settings.capability_post_mortem,
        organization_id=parsed.request.organization_id,
        capability_version=parsed.request.capability_version,
        user_texts=parsed.user_texts,
        canonical_input=parsed.request.model_dump(mode="json"),
        idempotency=parsed.idempotency,
    )
    return admit(door, runtime)


def assemble(parsed: Parsed, runtime: RuntimeContext) -> GenerateRequest:
    """Stage 4: the prompt file, filled; the incident and the timeline fenced as data."""
    request = parsed.request
    prompt = PromptFile.load(PROMPT_PATH)
    developer = fill(prompt.section("developer"), {"language": request.language or PRESERVE})
    segments = [
        Segment(role="system", name="system", text=prompt.section("system")),
        Segment(role="developer", name="developer", text=developer),
        Segment(
            role="user",
            name="incident",
            text=fence("incident", parsed.user_texts["incident"] or ABSENT),
        ),
        Segment(
            role="user",
            name="timeline",
            text=fence("timeline", parsed.user_texts["timeline"] or ABSENT),
        ),
    ]
    timeout = runtime.settings.capability_post_mortem.timeout_ms or descriptor.timeout_ms
    return GenerateRequest(
        organization_id=request.organization_id,
        request_id=parsed.request_id,
        capability=descriptor.name,
        alias=ModelAlias(descriptor.alias),
        segments=segments,
        output_schema=output_schema(),
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
) -> tuple[ModelOutput, GenerateResult]:
    """Stage 6: parse against the schema with one repair attempt; then the leakage scan."""
    output, current = await parse_with_repair(result, ModelOutput, lambda: call(generate, runtime))
    texts = [text for text in parsed.user_texts.values() if text]
    refuse_if_unsafe(prose_of(output), texts, parsed.request_id)
    return output, current


def postprocess(
    output: ModelOutput, result: GenerateResult, parsed: Parsed, runtime: RuntimeContext
) -> PostMortemResponse:
    """Stage 7: settle the spend; traceability, the tokens, the facts in order, the response."""
    runtime.budgets.settle(parsed.request.organization_id, result.usage.cost_micros)
    return to_response(output, result, parsed.request, parsed.request_id)


def _cache_ttl(runtime: RuntimeContext) -> int:
    ttl = runtime.settings.capability_post_mortem.cache_ttl_seconds
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
    request: PostMortemRequest,
    runtime: RuntimeContext,
    request_id: str,
    idempotency: str | None = None,
) -> PostMortemResponse:
    """Run the stages in order, with the cache in front of the call."""
    return await run_stages(STAGES, request, runtime, request_id, idempotency)
