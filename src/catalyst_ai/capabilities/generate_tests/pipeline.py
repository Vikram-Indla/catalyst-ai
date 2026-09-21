"""The generate-tests pipeline: parse, validate, assemble, call, validate_output, postprocess."""

from dataclasses import dataclass
from pathlib import Path

from catalyst_ai.capabilities.generate_tests import descriptor
from catalyst_ai.capabilities.generate_tests.postprocess import from_cache, to_response
from catalyst_ai.capabilities.generate_tests.schema import ModelOutput, output_schema, prose_of
from catalyst_ai.contract.errors import ErrorCode, ErrorDetail
from catalyst_ai.contract.generate_tests import (
    ExistingCase,
    GenerateTestsRequest,
    GenerateTestsResponse,
)
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.pipeline import Door, Stages, admit, parse_with_repair, run_stages
from catalyst_ai.platform.prompts import PromptFile, fill
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.platform.safety import fence, refuse_if_unsafe
from catalyst_ai.providers.port import GenerateRequest, GenerateResult, ModelAlias, Segment

PROMPT_PATH = Path(__file__).with_name(f"prompt_v{descriptor.prompt_version}.md")
ABSENT = "(none)"
PRESERVE = "the story's own"
CASES_REQUIRED = "cases_required"


@dataclass(frozen=True)
class Parsed:
    """The request plus the texts the door scans and the prompt fences."""

    request: GenerateTestsRequest
    request_id: str
    idempotency: str | None
    user_texts: dict[str, str | None]


def story_text(request: GenerateTestsRequest) -> str:
    """Return the story's key, title and description, one per line."""
    story = request.story
    lines = [f"key: {story.key}"] if story.key else []
    lines.append(f"title: {story.title}")
    if story.description:
        lines.append(f"description: {story.description}")
    return "\n".join(lines)


def criteria_text(request: GenerateTestsRequest) -> str:
    """One line per criterion: the id a case cites, then the text."""
    return "\n".join(f"[{c.id}] {c.text}" for c in request.criteria)


def _case_lines(case: ExistingCase) -> list[str]:
    head = f"[{case.id}] {case.title}" + (f" — {case.objective}" if case.objective else "")
    return [head, *(f"  step: {s.action} -> {s.expected}" for s in case.steps)]


def cases_text(request: GenerateTestsRequest) -> str:
    """One block per existing case: the id a table cites, the title, the steps."""
    return "\n".join(line for case in request.cases for line in _case_lines(case))


def require_cases(request: GenerateTestsRequest) -> None:
    """Artefacts are built from cases; a request without any is refused at the door."""
    if request.mode.value == "artefacts" and not request.cases:
        detail = ErrorDetail(field="cases", code=CASES_REQUIRED, message="artefacts need cases")
        raise Error(ErrorCode.INPUT_REJECTED, "the request carries no cases", details=[detail])


def parse(request: GenerateTestsRequest, request_id: str, idempotency: str | None) -> Parsed:
    """Stage 1: the typed request becomes the pipeline's input; the lists become texts."""
    texts: dict[str, str | None] = {
        "story": story_text(request),
        "criteria": criteria_text(request) or None,
        "cases": cases_text(request) or None,
    }
    return Parsed(request, request_id, idempotency, texts)


def validate(parsed: Parsed, runtime: RuntimeContext) -> str:
    """Stage 2: the cases the mode needs, then the door — switch, version, scanner, cap."""
    require_cases(parsed.request)
    door = Door(
        name=descriptor.name,
        version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        alias=descriptor.alias,
        settings=runtime.settings.capability_generate_tests,
        organization_id=parsed.request.organization_id,
        capability_version=parsed.request.capability_version,
        user_texts=parsed.user_texts,
        canonical_input=parsed.request.model_dump(mode="json"),
        idempotency=parsed.idempotency,
    )
    return admit(door, runtime)


def _mode_section(prompt: PromptFile, mode: str) -> str:
    return prompt.section("mode:" + mode)


def assemble(parsed: Parsed, runtime: RuntimeContext) -> GenerateRequest:
    """Stage 4: the prompt file, filled; the story, the criteria and the cases fenced as data."""
    request = parsed.request
    prompt = PromptFile.load(PROMPT_PATH)
    developer = fill(
        prompt.section("developer"),
        {
            "mode": request.mode.value,
            "max_cases": str(request.max_cases),
            "language": request.language or PRESERVE,
            "instructions": _mode_section(prompt, request.mode.value),
        },
    )
    segments = [
        Segment(role="system", name="system", text=prompt.section("system")),
        Segment(role="developer", name="developer", text=developer),
        Segment(role="user", name="story", text=fence("story", parsed.user_texts["story"] or "")),
        Segment(
            role="user",
            name="criteria",
            text=fence("criteria", parsed.user_texts["criteria"] or ABSENT),
        ),
        Segment(
            role="user", name="cases", text=fence("cases", parsed.user_texts["cases"] or ABSENT)
        ),
    ]
    timeout = runtime.settings.capability_generate_tests.timeout_ms or descriptor.timeout_ms
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
) -> GenerateTestsResponse:
    """Stage 7: settle the spend; traceability, the bounds, the gaps, the response."""
    runtime.budgets.settle(parsed.request.organization_id, result.usage.cost_micros)
    return to_response(output, result, parsed.request, parsed.request_id)


def _cache_ttl(runtime: RuntimeContext) -> int:
    ttl = runtime.settings.capability_generate_tests.cache_ttl_seconds
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
    request: GenerateTestsRequest,
    runtime: RuntimeContext,
    request_id: str,
    idempotency: str | None = None,
) -> GenerateTestsResponse:
    """Run the stages in order, with the cache in front of the call."""
    return await run_stages(STAGES, request, runtime, request_id, idempotency)
