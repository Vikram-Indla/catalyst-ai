"""The improve-story pipeline: parse, validate, assemble, call, validate_output, postprocess."""

from dataclasses import dataclass
from pathlib import Path

from catalyst_ai.capabilities.improve_story import descriptor
from catalyst_ai.capabilities.improve_story.comments import markup_problem
from catalyst_ai.capabilities.improve_story.governed import problems
from catalyst_ai.capabilities.improve_story.postprocess import from_cache, to_response
from catalyst_ai.capabilities.improve_story.schema import ModelOutput, output_schema
from catalyst_ai.contract.errors import ErrorCode, ErrorDetail
from catalyst_ai.contract.improve_story import ImproveStoryRequest, ImproveStoryResponse
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.language import latin
from catalyst_ai.platform.pipeline import Door, Stages, admit, parse_with_repair, run_stages
from catalyst_ai.platform.prompts import PromptFile, fill
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.platform.safety import fence, refuse_if_unsafe
from catalyst_ai.providers.port import GenerateRequest, GenerateResult, ModelAlias, Segment

PROMPT_PATH = Path(__file__).with_name(f"prompt_v{descriptor.prompt_version}.md")
USER_FIELDS = (
    "title",
    "description",
    "acceptance_criteria",
    "focus_hint",
    "parent_title",
    "parent_description",
    "comment",
)
RECORD_FIELDS = ("record_focus", "record_context", "glossary")
ABSENT = "(none)"
PRESERVE = "preserve the input's language"
NO_AUTHOR = "(no comment)"


@dataclass(frozen=True)
class Parsed:
    """The request plus what the run needs to remember about it."""

    request: ImproveStoryRequest
    request_id: str
    idempotency: str | None
    user_texts: dict[str, str | None]


def parse(request: ImproveStoryRequest, request_id: str, idempotency: str | None) -> Parsed:
    """Stage 1: the typed request becomes the pipeline's input value."""
    texts = {name: getattr(request, name) for name in USER_FIELDS if name != "comment"}
    texts["comment"] = request.comment.text if request.comment else None
    texts.update(_record_texts(request))
    return Parsed(request, request_id, idempotency, texts)


def _record_texts(request: ImproveStoryRequest) -> dict[str, str | None]:
    """Return a governed record's focus, context and glossary as texts; none without a record."""
    record = request.record
    if record is None:
        return {}
    context = "\n".join(f"{line.label}: {line.text}" for line in record.context)
    return {
        "record_focus": record.focus,
        "record_context": context or None,
        "glossary": "\n".join(record.glossary) or None,
    }


def validate(parsed: Parsed, runtime: RuntimeContext) -> str:
    """Stage 2: the door — switch, contract version, scanner, tenant cap; return the cache key."""
    door = Door(
        name=descriptor.name,
        version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        alias=descriptor.alias,
        settings=runtime.settings.capability_improve_story,
        organization_id=parsed.request.organization_id,
        capability_version=parsed.request.capability_version,
        user_texts=parsed.user_texts,
        canonical_input=parsed.request.model_dump(mode="json"),
        idempotency=parsed.idempotency,
    )
    return admit(door, runtime)


def _focus_section(prompt: PromptFile, request: ImproveStoryRequest) -> str:
    if request.record is not None:
        return prompt.section("focus:record")
    return prompt.sections.get(f"focus:{request.item_type}", prompt.section("focus:default"))


def _record_segments(prompt: PromptFile, parsed: Parsed) -> list[Segment]:
    """Return the record's rule and its focus, context and glossary, each fenced as data."""
    segments = [Segment(role="developer", name="record", text=prompt.section("developer:record"))]
    for name in RECORD_FIELDS:
        text = parsed.user_texts.get(name) or ABSENT
        segments.append(Segment(role="user", name=name, text=fence(name, text)))
    return segments


def _operation_section(prompt: PromptFile, mode: str) -> str:
    return prompt.section(f"operation:{mode}")


def assemble(parsed: Parsed, runtime: RuntimeContext) -> GenerateRequest:
    """Stage 4: the prompt file, filled; every user field fenced as data."""
    request = parsed.request
    prompt = PromptFile.load(PROMPT_PATH)
    developer = fill(
        prompt.section("developer"),
        {
            "item_type": fence("item_type", request.item_type),
            "type_focus": _focus_section(prompt, request),
            "operation": request.mode.value,
            "language": request.language or PRESERVE,
            "comment_author": request.comment.participant if request.comment else NO_AUTHOR,
            "instructions": _operation_section(prompt, request.mode.value),
        },
    )
    segments = [
        Segment(role="system", name="system", text=prompt.section("system")),
        Segment(role="developer", name="developer", text=developer),
    ]
    for name in USER_FIELDS:
        text = parsed.user_texts.get(name) or ABSENT
        segments.append(Segment(role="user", name=name, text=fence(name, text)))
    if request.record is not None:
        segments.extend(_record_segments(prompt, parsed))
    timeout = runtime.settings.capability_improve_story.timeout_ms or descriptor.timeout_ms
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
    completion = output.description + "\n" + (output.acceptance_criteria or "")
    refuse_if_unsafe(completion, texts, parsed.request_id)
    _refuse_broken_markup(parsed, output.description)
    if parsed.request.record is not None:
        output = _in_latin_digits(output)
        _refuse_changed_facts(parsed, output)
    return output, current


def _in_latin_digits(output: ModelOutput) -> ModelOutput:
    criteria = output.acceptance_criteria
    return output.model_copy(
        update={
            "description": latin(output.description),
            "acceptance_criteria": None if criteria is None else latin(criteria),
        }
    )


def _refuse_changed_facts(parsed: Parsed, output: ModelOutput) -> None:
    """Refuse a governed record's rewrite that adds a fact or loses a glossary term."""
    found = problems(parsed.request, output.description + "\n" + (output.acceptance_criteria or ""))
    if found:
        details = [
            ErrorDetail(field="improved_description", code=code, message=f"{code}: {what}")
            for code, what in found
        ]
        raise Error(ErrorCode.OUTPUT_INVALID, "the record's facts were not kept", details=details)


def _refuse_broken_markup(parsed: Parsed, text: str) -> None:
    """Refuse a comment mode's output that dropped markup or named someone new."""
    request = parsed.request
    if request.comment is None:
        return
    context = request.title + "\n" + request.description
    problem = markup_problem(request.mode, request.comment, context, text)
    if problem is not None:
        detail = ErrorDetail(field="improved_description", code=problem, message=problem)
        raise Error(ErrorCode.OUTPUT_INVALID, "the comment's markup was not kept", details=[detail])


def postprocess(
    output: ModelOutput, result: GenerateResult, parsed: Parsed, runtime: RuntimeContext
) -> ImproveStoryResponse:
    """Stage 7: settle the spend, log the row, map to the response model."""
    runtime.budgets.settle(parsed.request.organization_id, result.usage.cost_micros)
    return to_response(output, result, parsed.request, parsed.request_id)


def _cache_ttl(runtime: RuntimeContext) -> int:
    ttl = runtime.settings.capability_improve_story.cache_ttl_seconds
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
    request: ImproveStoryRequest,
    runtime: RuntimeContext,
    request_id: str,
    idempotency: str | None = None,
) -> ImproveStoryResponse:
    """Run the stages in order, with the cache in front of the call."""
    return await run_stages(STAGES, request, runtime, request_id, idempotency)
