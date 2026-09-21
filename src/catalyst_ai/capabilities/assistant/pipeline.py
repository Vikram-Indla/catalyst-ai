"""The turn pipeline: parse, validate, retrieve over the spaces, assemble, call, cite, respond.

`run` answers whole; `stream` answers as frames through the platform's streaming runner. Both
share every stage: the call is the only difference, and the port is touched nowhere else.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass, replace
from pathlib import Path

from catalyst_ai.capabilities.assistant import descriptor
from catalyst_ai.capabilities.assistant.reply import from_cache, to_response
from catalyst_ai.capabilities.assistant.schema import Output, split, visible
from catalyst_ai.capabilities.assistant.sources import (
    ABSENT,
    Source,
    check_reply,
    number_sources,
    sources_text,
)
from catalyst_ai.contract.assistant import TurnRequest, TurnResponse
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.pipeline import (
    Door,
    Event,
    Stages,
    admit,
    run_stages,
    run_streaming,
)
from catalyst_ai.platform.pipeline.output import REPAIR_ATTEMPTS, merge_usage
from catalyst_ai.platform.prompts import PromptFile, fill
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.platform.safety import fence, refuse_if_unsafe
from catalyst_ai.providers.port import GenerateRequest, GenerateResult, ModelAlias, Segment
from catalyst_ai.retrieval import DOCUMENTS, Grounding, Passage, retrieve, space_prefix

PROMPT_PATH = Path(__file__).with_name(f"prompt_v{descriptor.prompt_version}.md")
PRESERVE = "the thread's own"
PER_SPACE_K = 6
MAX_PASSAGES = 12
NOT_MATCHED = "the completion did not carry its tail"


@dataclass(frozen=True)
class Parsed:
    """The request, the texts the door scans, the sources once numbered."""

    request: TurnRequest
    request_id: str
    idempotency: str | None
    user_texts: dict[str, str | None]
    sources: tuple[Source, ...] = ()
    retrieval_cost_micros: int = 0


def thread_text(request: TurnRequest) -> str:
    """Return the thread as the prompt reads it: the summary first, then one line per turn."""
    lines = [f"summary: {request.summary}"] if request.summary else []
    lines += [f"{turn.role}: {turn.text}" for turn in request.history]
    return "\n".join(lines)


def parse(request: TurnRequest, request_id: str, idempotency: str | None) -> Parsed:
    """Stage 1: the typed request becomes the pipeline's input; every member text is scanned."""
    texts: dict[str, str | None] = {
        "thread": thread_text(request),
        "items": "\n".join(f"{i.title}\n{i.summary or ''}" for i in request.context.items) or None,
        "pages": "\n".join(p.text for p in request.context.pages) or None,
    }
    return Parsed(request, request_id, idempotency, texts)


def validate(parsed: Parsed, runtime: RuntimeContext) -> str:
    """Stage 2: the door — switch, version, scanner, tenant cap; return the cache key."""
    door = Door(
        name=descriptor.name,
        version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        alias=descriptor.alias,
        settings=runtime.settings.capability_assistant,
        organization_id=parsed.request.organization_id,
        capability_version=parsed.request.capability_version,
        user_texts=parsed.user_texts,
        canonical_input=parsed.request.model_dump(mode="json"),
        idempotency=parsed.idempotency,
    )
    return admit(door, runtime)


def timeout_ms(runtime: RuntimeContext) -> int:
    """Return the per-call deadline: the settings override the descriptor."""
    return runtime.settings.capability_assistant.timeout_ms or descriptor.timeout_ms


async def retrieve_sources(parsed: Parsed, runtime: RuntimeContext) -> Parsed:
    """Stage 3: the spaces' passages for the last turn, then every source numbered."""
    request = parsed.request
    passages: list[Passage] = []
    cost = 0
    for space in request.context.spaces:
        grounding = Grounding(
            organization_id=request.organization_id,
            spec=DOCUMENTS,
            capability=descriptor.name,
            timeout_ms=timeout_ms(runtime),
            question=request.history[-1].text,
            prefix=space_prefix(space.space_id),
            kinds=(),
            k=PER_SPACE_K,
        )
        found = await retrieve(grounding, runtime.storage, runtime.provider)
        cost += found.usage.cost_micros
        passages += [p for p in found.passages if found.found]
    ranked = sorted(passages, key=lambda p: -p.score)[:MAX_PASSAGES]
    sources = number_sources(ranked, request.context)
    texts = {**parsed.user_texts, "sources": sources_text(sources) or None}
    return replace(parsed, sources=tuple(sources), user_texts=texts, retrieval_cost_micros=cost)


def assemble(parsed: Parsed, runtime: RuntimeContext) -> GenerateRequest:
    """Stage 4: the prompt file, filled; the thread and the sources fenced as data."""
    request = parsed.request
    prompt = PromptFile.load(PROMPT_PATH)
    developer = fill(prompt.section("developer"), {"language": request.language or PRESERVE})
    segments = [
        Segment(role="system", name="system", text=prompt.section("system")),
        Segment(role="developer", name="developer", text=developer),
        Segment(role="user", name="thread", text=fence("thread", thread_text(request))),
        Segment(
            role="user",
            name="sources",
            text=fence("sources", parsed.user_texts.get("sources") or ABSENT),
        ),
    ]
    return GenerateRequest(
        organization_id=request.organization_id,
        request_id=parsed.request_id,
        capability=descriptor.name,
        alias=ModelAlias(descriptor.alias),
        segments=segments,
        output_schema=None,
        temperature=descriptor.temperature,
        max_output_tokens=descriptor.max_output_tokens,
        timeout_ms=timeout_ms(runtime),
    )


async def call(generate: GenerateRequest, runtime: RuntimeContext) -> GenerateResult:
    """Stage 5: the one provider call, inside the tenant's concurrency slot."""
    async with runtime.budgets.slot(generate.organization_id):
        return await runtime.provider.generate(generate)


async def validate_output(
    result: GenerateResult, generate: GenerateRequest, parsed: Parsed, runtime: RuntimeContext
) -> tuple[Output, GenerateResult]:
    """Stage 6: split prose and tail with one repair; then the leakage scan and the citations."""
    current, attempts = result, 0
    while True:
        try:
            prose, tail = split(current.text)
            break
        except ValueError as error:
            attempts += 1
            if attempts > REPAIR_ATTEMPTS:
                raise Error(ErrorCode.OUTPUT_INVALID, NOT_MATCHED) from error
            current = merge_usage(current, await call(generate, runtime))
    texts = [text for text in parsed.user_texts.values() if text]
    refuse_if_unsafe(f"{prose}\n{tail.rationale}", texts, parsed.request_id)
    check_reply(prose, list(parsed.sources), not_found=tail.not_found)
    return Output(prose, tail), current


def postprocess(
    output: Output, result: GenerateResult, parsed: Parsed, runtime: RuntimeContext
) -> TurnResponse:
    """Stage 7: settle the spend; the reply with its citations and sources."""
    spent = result.usage.cost_micros + parsed.retrieval_cost_micros
    runtime.budgets.settle(parsed.request.organization_id, spent)
    return to_response(output, result, list(parsed.sources), parsed.request, parsed.request_id)


def _cache_ttl(runtime: RuntimeContext) -> int:
    ttl = runtime.settings.capability_assistant.cache_ttl_seconds
    return descriptor.cache_ttl_seconds if ttl is None else ttl


STAGES = Stages(
    parse=parse,
    validate=validate,
    retrieve=retrieve_sources,
    assemble=assemble,
    call=call,
    validate_output=validate_output,
    postprocess=postprocess,
    from_cache=from_cache,
    cache_ttl=_cache_ttl,
)


async def run(
    request: TurnRequest, runtime: RuntimeContext, request_id: str, idempotency: str | None = None
) -> TurnResponse:
    """Answer one turn whole, with the cache in front of the call."""
    return await run_stages(STAGES, request, runtime, request_id, idempotency)


def stream(
    request: TurnRequest, runtime: RuntimeContext, request_id: str
) -> AsyncIterator[Event[TurnResponse]]:
    """Answer one turn as events: the prose as it arrives, then the usage and the response."""
    return run_streaming(STAGES, request, runtime, request_id, visible)
