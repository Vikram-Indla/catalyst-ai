"""The summarize pipeline: parse, validate, assemble, call, validate_output, postprocess."""

from dataclasses import dataclass
from pathlib import Path

from catalyst_ai.capabilities.summarize import descriptor
from catalyst_ai.capabilities.summarize.modes import (
    counts_text,
    require_window,
    window_text,
    within_window,
)
from catalyst_ai.capabilities.summarize.postprocess import from_cache, to_response
from catalyst_ai.capabilities.summarize.schema import ModelOutput, output_schema, prose_of
from catalyst_ai.contract.summarize import SummarizeRequest, SummarizeResponse, ThreadItem
from catalyst_ai.platform.pipeline import Door, Stages, admit, parse_with_repair, run_stages
from catalyst_ai.platform.prompts import PromptFile, fill
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.platform.safety import fence, refuse_if_unsafe
from catalyst_ai.providers.port import GenerateRequest, GenerateResult, ModelAlias, Segment

PROMPT_PATH = Path(__file__).with_name(f"prompt_v{descriptor.prompt_version}.md")
ABSENT = "(none)"
PRESERVE = "the thread's own"
CAP_SHARE = 1.5


@dataclass(frozen=True)
class Parsed:
    """The request plus the texts the door scans and the prompt fences."""

    request: SummarizeRequest
    request_id: str
    idempotency: str | None
    user_texts: dict[str, str | None]


def _item_line(item: ThreadItem) -> str:
    kind = f" ({item.kind})" if item.kind else ""
    return f"[{item.id}] {item.participant}{kind} @ {item.at.isoformat()}: {item.text}"


def thread_text(request: SummarizeRequest) -> str:
    """One line per item: the id, the token, the kind, the time, the text — as the prompt reads."""
    return "\n".join(_item_line(item) for item in request.items)


def status_text(request: SummarizeRequest) -> str:
    """One line per recorded move."""
    return "\n".join(
        f"{c.participant} moved it from {c.from_status or 'unset'} to {c.to_status}"
        f" at {c.at.isoformat()}"
        for c in request.status_changes
    )


def parse(request: SummarizeRequest, request_id: str, idempotency: str | None) -> Parsed:
    """Stage 1: the typed request, cut to its window, becomes the input; the thread one text."""
    request = within_window(request)
    texts: dict[str, str | None] = {
        "thread": thread_text(request) or None,
        "status_changes": status_text(request) or None,
        "item_title": request.item_title,
    }
    return Parsed(request, request_id, idempotency, texts)


def validate(parsed: Parsed, runtime: RuntimeContext) -> str:
    """Stage 2: the window the mode needs, then the door — switch, version, scanner, cap."""
    require_window(parsed.request)
    door = Door(
        name=descriptor.name,
        version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        alias=descriptor.alias,
        settings=runtime.settings.capability_summarize,
        organization_id=parsed.request.organization_id,
        capability_version=parsed.request.capability_version,
        user_texts=parsed.user_texts,
        canonical_input=parsed.request.model_dump(mode="json"),
        idempotency=parsed.idempotency,
    )
    return admit(door, runtime)


def _focus(prompt: PromptFile, item_type: str | None) -> str:
    return prompt.sections.get(f"focus:{item_type}", prompt.section("focus:default"))


def _mode_section(prompt: PromptFile, mode: str) -> str:
    return prompt.section("mode:" + mode)


def assemble(parsed: Parsed, runtime: RuntimeContext) -> GenerateRequest:
    """Stage 4: the prompt file, filled; the thread and the status changes fenced as data."""
    request = parsed.request
    prompt = PromptFile.load(PROMPT_PATH)
    developer = fill(
        prompt.section("developer"),
        {
            "mode": request.mode.value,
            "item_title": fence("item_title", request.item_title or ABSENT),
            "item_type": fence("item_type", request.item_type or ABSENT),
            "focus": _focus(prompt, request.item_type),
            "target_words": str(request.target_words),
            "max_words": str(int(request.target_words * CAP_SHARE)),
            "language": request.language or PRESERVE,
            "window": window_text(request) or ABSENT,
            "counts": counts_text(request) or ABSENT,
            "instructions": _mode_section(prompt, request.mode.value),
        },
    )
    segments = [
        Segment(role="system", name="system", text=prompt.section("system")),
        Segment(role="developer", name="developer", text=developer),
        Segment(
            role="user", name="thread", text=fence("thread", parsed.user_texts["thread"] or ABSENT)
        ),
        Segment(
            role="user",
            name="status_changes",
            text=fence("status_changes", parsed.user_texts["status_changes"] or ABSENT),
        ),
    ]
    timeout = runtime.settings.capability_summarize.timeout_ms or descriptor.timeout_ms
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
) -> SummarizeResponse:
    """Stage 7: settle the spend; the participant rule, the cap, the range, the response."""
    runtime.budgets.settle(parsed.request.organization_id, result.usage.cost_micros)
    return to_response(output, result, parsed.request, parsed.request_id)


def _cache_ttl(runtime: RuntimeContext) -> int:
    ttl = runtime.settings.capability_summarize.cache_ttl_seconds
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
    request: SummarizeRequest,
    runtime: RuntimeContext,
    request_id: str,
    idempotency: str | None = None,
) -> SummarizeResponse:
    """Run the stages in order, with the cache in front of the call."""
    return await run_stages(STAGES, request, runtime, request_id, idempotency)
