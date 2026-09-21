"""The generate-children pipeline: parse, validate, retrieve, assemble, call, validate, post."""

from dataclasses import dataclass
from pathlib import Path

from catalyst_ai.capabilities.generate_children import descriptor
from catalyst_ai.capabilities.generate_children.postprocess import (
    expected_child_level,
    from_cache,
    to_response,
)
from catalyst_ai.capabilities.generate_children.retrieve import indexed_siblings
from catalyst_ai.capabilities.generate_children.schema import ModelOutput, output_schema
from catalyst_ai.contract.generate_children import (
    GenerateChildrenRequest,
    GenerateChildrenResponse,
)
from catalyst_ai.platform.pipeline import Door, Stages, admit, parse_with_repair, run_stages
from catalyst_ai.platform.prompts import PromptFile, fill
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.platform.safety import fence, refuse_if_unsafe
from catalyst_ai.providers.port import GenerateRequest, GenerateResult, ModelAlias, Segment

PROMPT_PATH = Path(__file__).with_name(f"prompt_v{descriptor.prompt_version}.md")
ABSENT = "(none)"
PRESERVE = "preserve the input's language"
LIST_SEPARATOR = "\n- "


@dataclass(frozen=True)
class Parsed:
    """The request plus the texts the door scans and the prompt fences."""

    request: GenerateChildrenRequest
    request_id: str
    idempotency: str | None
    user_texts: dict[str, str | None]
    indexed_siblings: tuple[str, ...] | None = None


def parse(request: GenerateChildrenRequest, request_id: str, idempotency: str | None) -> Parsed:
    """Stage 1: the typed request becomes the pipeline's input value; lists become one text each."""
    texts: dict[str, str | None] = {
        "parent_title": request.parent_title,
        "parent_description": request.parent_description,
        "source_texts": LIST_SEPARATOR.join(request.source_texts) if request.source_texts else None,
        "siblings": LIST_SEPARATOR.join(s.title for s in request.siblings)
        if request.siblings
        else None,
        "focus_hint": request.focus_hint,
    }
    return Parsed(request, request_id, idempotency, texts)


def validate(parsed: Parsed, runtime: RuntimeContext) -> str:
    """Stage 2: the door — switch, version, hierarchy, scanner, tenant cap; return the cache key."""
    expected_child_level(parsed.request)
    door = Door(
        name=descriptor.name,
        version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        alias=descriptor.alias,
        settings=runtime.settings.capability_generate_children,
        organization_id=parsed.request.organization_id,
        capability_version=parsed.request.capability_version,
        user_texts=parsed.user_texts,
        canonical_input=parsed.request.model_dump(mode="json"),
        idempotency=parsed.idempotency,
    )
    return admit(door, runtime)


async def retrieve(parsed: Parsed, runtime: RuntimeContext) -> Parsed:
    """Stage 3: the tenant's indexed items at the child level join the sibling pool."""
    found = await indexed_siblings(parsed.request, expected_child_level(parsed.request), runtime)
    if found is None:
        return parsed
    return Parsed(
        parsed.request,
        parsed.request_id,
        parsed.idempotency,
        parsed.user_texts,
        indexed_siblings=found,
    )


def _target_section(prompt: PromptFile, target: str) -> str:
    return prompt.section(f"target:{target}")


def assemble(parsed: Parsed, runtime: RuntimeContext) -> GenerateRequest:
    """Stage 4: the prompt file, filled; the hierarchy as data; every user field fenced."""
    request = parsed.request
    prompt = PromptFile.load(PROMPT_PATH)
    developer = fill(
        prompt.section("developer"),
        {
            "target": request.target.value,
            "child_level": fence("child_level", expected_child_level(request)),
            "parent_level": fence("parent_level", request.parent_level),
            "hierarchy": fence("hierarchy", " > ".join(request.hierarchy)),
            "max_items": str(request.max_items),
            "language": request.language or PRESERVE,
            "instructions": _target_section(prompt, request.target.value),
        },
    )
    segments = [
        Segment(role="system", name="system", text=prompt.section("system")),
        Segment(role="developer", name="developer", text=developer),
    ]
    for name, text in parsed.user_texts.items():
        segments.append(Segment(role="user", name=name, text=fence(name, text or ABSENT)))
    timeout = runtime.settings.capability_generate_children.timeout_ms or descriptor.timeout_ms
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
    completion = "\n".join(
        c.title + "\n" + c.description + "\n" + "\n".join(c.acceptance_criteria)
        for c in output.candidates
    )
    refuse_if_unsafe(completion, texts, parsed.request_id)
    return output, current


def postprocess(
    output: ModelOutput, result: GenerateResult, parsed: Parsed, runtime: RuntimeContext
) -> GenerateChildrenResponse:
    """Stage 7: settle the spend; then the hierarchy check, de-duplication, bounding, response."""
    runtime.budgets.settle(parsed.request.organization_id, result.usage.cost_micros)
    return to_response(
        output,
        result,
        parsed.request,
        parsed.request_id,
        parsed.indexed_siblings,
    )


def _cache_ttl(runtime: RuntimeContext) -> int:
    ttl = runtime.settings.capability_generate_children.cache_ttl_seconds
    return descriptor.cache_ttl_seconds if ttl is None else ttl


STAGES = Stages(
    parse=parse,
    validate=validate,
    retrieve=retrieve,
    assemble=assemble,
    call=call,
    validate_output=validate_output,
    postprocess=postprocess,
    from_cache=from_cache,
    cache_ttl=_cache_ttl,
)


async def run(
    request: GenerateChildrenRequest,
    runtime: RuntimeContext,
    request_id: str,
    idempotency: str | None = None,
) -> GenerateChildrenResponse:
    """Run the stages in order, with the cache in front of the call."""
    return await run_stages(STAGES, request, runtime, request_id, idempotency)
