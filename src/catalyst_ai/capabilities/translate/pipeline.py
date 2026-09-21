"""The translate pipeline: parse, validate, assemble, call, validate_output, postprocess."""

from dataclasses import dataclass
from pathlib import Path

from catalyst_ai.capabilities.translate import descriptor
from catalyst_ai.capabilities.translate.postprocess import from_cache, to_response
from catalyst_ai.capabilities.translate.quality import detect_language
from catalyst_ai.capabilities.translate.schema import ModelOutput, output_schema
from catalyst_ai.contract.errors import ErrorCode, ErrorDetail
from catalyst_ai.contract.translate import TranslateRequest, TranslateResponse
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.pipeline import Door, Stages, admit, parse_with_repair, run_stages
from catalyst_ai.platform.prompts import PromptFile, fill
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.platform.safety import fence, refuse_if_unsafe
from catalyst_ai.providers.port import GenerateRequest, GenerateResult, ModelAlias, Segment

PROMPT_PATH = Path(__file__).with_name(f"prompt_v{descriptor.prompt_version}.md")
ABSENT = "(none)"
DETECT = "detect it"
TARGET_REQUIRED = "target_language_required"


@dataclass(frozen=True)
class Parsed:
    """The request plus the texts the door scans and the prompt fences."""

    request: TranslateRequest
    request_id: str
    idempotency: str | None
    user_texts: dict[str, str | None]


def parse(request: TranslateRequest, request_id: str, idempotency: str | None) -> Parsed:
    """Stage 1: the typed request becomes the pipeline's input value."""
    return Parsed(
        request, request_id, idempotency, {"text": request.text, "context": request.context}
    )


def require_target(request: TranslateRequest) -> str:
    """Return the target; a request without one is refused at the door."""
    if not request.target_language:
        detail = ErrorDetail(
            field="target_language", code=TARGET_REQUIRED, message="a translation names its target"
        )
        raise Error(
            ErrorCode.INPUT_REJECTED, "the request names no target language", details=[detail]
        )
    return request.target_language


def validate(parsed: Parsed, runtime: RuntimeContext) -> str:
    """Stage 2: the target, then the door — switch, version, scanner, tenant cap."""
    require_target(parsed.request)
    door = Door(
        name=descriptor.name,
        version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        alias=descriptor.alias,
        settings=runtime.settings.capability_translate,
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
    """Stage 4: the prompt file, filled; the text and the context fenced as data."""
    request = parsed.request
    prompt = PromptFile.load(PROMPT_PATH)
    developer = fill(
        prompt.section("developer"),
        {
            "mode": request.mode.value,
            "source_language": request.source_language or DETECT,
            "target_language": require_target(request),
            "instructions": _mode_section(prompt, request.mode.value),
        },
    )
    segments = [
        Segment(role="system", name="system", text=prompt.section("system")),
        Segment(role="developer", name="developer", text=developer),
        Segment(role="user", name="text", text=fence("text", request.text)),
        Segment(role="user", name="context", text=fence("context", request.context or ABSENT)),
    ]
    timeout = runtime.settings.capability_translate.timeout_ms or descriptor.timeout_ms
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
    refuse_if_unsafe(output.translated_text, texts, parsed.request_id)
    return output, current


def postprocess(
    output: ModelOutput, result: GenerateResult, parsed: Parsed, runtime: RuntimeContext
) -> TranslateResponse:
    """Stage 7: settle the spend; the detected language cross-checked; the response."""
    runtime.budgets.settle(parsed.request.organization_id, result.usage.cost_micros)
    detected = parsed.request.source_language or detect_language(parsed.request.text)
    return to_response(output, result, parsed.request, parsed.request_id, detected)


def _cache_ttl(runtime: RuntimeContext) -> int:
    ttl = runtime.settings.capability_translate.cache_ttl_seconds
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
    request: TranslateRequest,
    runtime: RuntimeContext,
    request_id: str,
    idempotency: str | None = None,
) -> TranslateResponse:
    """Run the stages in order, with the cache in front of the call."""
    return await run_stages(STAGES, request, runtime, request_id, idempotency)
