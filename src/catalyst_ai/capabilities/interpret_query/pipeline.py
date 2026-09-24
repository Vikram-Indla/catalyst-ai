"""The interpret-query pipeline: parse, validate, assemble, call, validate_output, postprocess."""

from dataclasses import dataclass
from pathlib import Path

from catalyst_ai.capabilities.interpret_query import descriptor
from catalyst_ai.capabilities.interpret_query.grammar import GrammarError, canonical
from catalyst_ai.capabilities.interpret_query.listing import listing_lines, normalise
from catalyst_ai.capabilities.interpret_query.postprocess import from_cache, to_response
from catalyst_ai.capabilities.interpret_query.schema import ModelOutput, output_schema
from catalyst_ai.contract.errors import ErrorCode, ErrorDetail
from catalyst_ai.contract.interpret_query import (
    Grammar,
    InterpretQueryRequest,
    InterpretQueryResponse,
)
from catalyst_ai.platform.errors import Error
from catalyst_ai.platform.pipeline import Door, Stages, admit, parse_with_repair, run_stages
from catalyst_ai.platform.pipeline.output import merge_usage
from catalyst_ai.platform.prompts import PromptFile, fill
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.platform.safety import fence, refuse_if_unsafe
from catalyst_ai.providers.port import GenerateRequest, GenerateResult, ModelAlias, Segment

PROMPT_PATH = Path(__file__).with_name(f"prompt_v{descriptor.prompt_version}.md")
NOT_IN_GRAMMAR = "query_not_in_grammar"
NOT_DECLARED = "parameters_not_declared"
ANY_VALUE = "any value of its type"


@dataclass(frozen=True)
class Parsed:
    """The request plus the texts the door scans and the prompt fences."""

    request: InterpretQueryRequest
    request_id: str
    idempotency: str | None
    user_texts: dict[str, str | None]


def grammar_lines(grammar: Grammar) -> str:
    """Write the grammar for the prompt: one line per field, its type, operators and values."""
    lines = []
    for spec in grammar.fields:
        values = " | ".join(spec.values) if spec.values is not None else ANY_VALUE
        lines.append(f"- {spec.name} ({spec.type}; {', '.join(spec.operators)}): {values}")
    return "\n".join(lines)


def parse(request: InterpretQueryRequest, request_id: str, idempotency: str | None) -> Parsed:
    """Stage 1: the typed request becomes the pipeline's input value."""
    return Parsed(request, request_id, idempotency, {"text": request.text})


def validate(parsed: Parsed, runtime: RuntimeContext) -> str:
    """Stage 2: the door — switch, version, scanner, tenant cap; return the cache key."""
    door = Door(
        name=descriptor.name,
        version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        alias=descriptor.alias,
        settings=runtime.settings.capability_interpret_query,
        organization_id=parsed.request.organization_id,
        capability_version=parsed.request.capability_version,
        user_texts=parsed.user_texts,
        canonical_input=parsed.request.model_dump(mode="json"),
        idempotency=parsed.idempotency,
    )
    return admit(door, runtime)


def assemble(parsed: Parsed, runtime: RuntimeContext) -> GenerateRequest:
    """Stage 4: the prompt file, filled with the grammar; the sentence fenced as data."""
    request = parsed.request
    prompt = PromptFile.load(PROMPT_PATH)
    moment = {
        "now": request.now.isoformat(),
        "timezone": request.timezone,
        "locale": request.locale,
    }
    if request.listing is not None:
        filled = {**moment, "listing": listing_lines(request.listing)}
        developer = fill(prompt.section("developer:listing"), filled)
    else:
        grammar = request.grammar or Grammar.model_construct(fields=[], functions=[])
        filled = {
            **moment,
            "grammar": grammar_lines(grammar),
            "functions": ", ".join(f.name for f in grammar.functions) or "(none)",
        }
        developer = fill(prompt.section("developer"), filled)
    segments = [
        Segment(role="system", name="system", text=prompt.section("system")),
        Segment(role="developer", name="developer", text=developer),
        Segment(role="user", name="sentence", text=fence("sentence", request.text)),
    ]
    timeout = runtime.settings.capability_interpret_query.timeout_ms or descriptor.timeout_ms
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


def output_problems(output: ModelOutput, request: InterpretQueryRequest) -> list[str]:
    """Return why the answer is outside what the request allows: its declaration or its grammar."""
    if request.listing is not None:
        return normalise(output.parameters, output.sort, request.listing)[2]
    grammar = request.grammar or Grammar.model_construct(fields=[], functions=[])
    return grammar_problems(output, grammar)


def grammar_problems(output: ModelOutput, grammar: Grammar) -> list[str]:
    """Return why the query is not in the grammar; an empty query is allowed and has none."""
    if not output.query.strip():
        return []
    try:
        canonical(output.query, grammar)
    except GrammarError as error:
        return error.problems
    return []


async def validate_output(
    result: GenerateResult, generate: GenerateRequest, parsed: Parsed, runtime: RuntimeContext
) -> tuple[ModelOutput, GenerateResult]:
    """Stage 6: the schema, then the grammar, each with one repair; then the leakage scan."""

    async def repair() -> GenerateResult:
        return await call(generate, runtime)

    output, current = await parse_with_repair(result, ModelOutput, repair)
    request = parsed.request
    if output_problems(output, request):
        retried, again = await parse_with_repair(await repair(), ModelOutput, repair)
        output, current = retried, merge_usage(current, again)
    problems = output_problems(output, request)
    if problems:
        listed = request.listing is not None
        field, code = ("parameters", NOT_DECLARED) if listed else ("query", NOT_IN_GRAMMAR)
        details = [
            ErrorDetail(field=field, code=code, message=problem.split(":", 1)[0])
            for problem in problems
        ]
        raise Error(
            ErrorCode.OUTPUT_INVALID, "the answer is outside what the list allows", details=details
        )
    refuse_if_unsafe(output.explanation, [parsed.request.text], parsed.request_id)
    return output, current


def postprocess(
    output: ModelOutput, result: GenerateResult, parsed: Parsed, runtime: RuntimeContext
) -> InterpretQueryResponse:
    """Stage 7: settle the spend; the query written canonically; the response."""
    runtime.budgets.settle(parsed.request.organization_id, result.usage.cost_micros)
    return to_response(output, result, parsed.request, parsed.request_id)


def _cache_ttl(runtime: RuntimeContext) -> int:
    ttl = runtime.settings.capability_interpret_query.cache_ttl_seconds
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
    request: InterpretQueryRequest,
    runtime: RuntimeContext,
    request_id: str,
    idempotency: str | None = None,
) -> InterpretQueryResponse:
    """Run the stages in order, with the cache in front of the call."""
    return await run_stages(STAGES, request, runtime, request_id, idempotency)
