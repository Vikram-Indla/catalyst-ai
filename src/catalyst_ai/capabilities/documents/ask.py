"""The ask pipeline: parse, validate, retrieve the space's passages, assemble, call, cite."""

from dataclasses import dataclass, replace
from pathlib import Path

from catalyst_ai.capabilities.documents import descriptor
from catalyst_ai.capabilities.documents.citations import from_cache, not_found_response, to_response
from catalyst_ai.capabilities.documents.schema import AskOutput, ask_prose, ask_schema
from catalyst_ai.contract.documents import AskRequest, AskResponse
from catalyst_ai.platform.pipeline import Door, Stages, admit, parse_with_repair, run_stages
from catalyst_ai.platform.prompts import PromptFile, fill
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.platform.safety import fence, refuse_if_unsafe
from catalyst_ai.providers.port import GenerateRequest, GenerateResult, ModelAlias, Segment
from catalyst_ai.retrieval import DOCUMENTS, Grounding, Passage, Retrieved, retrieve, space_prefix
from catalyst_ai.retrieval.embeddings import NO_USAGE

PROMPT_PATH = Path(__file__).with_name(f"prompt_v{descriptor.prompt_version}.md")
ABSENT = "(none)"
PRESERVE = "the question's own"
HEADING_JOIN = " > "


@dataclass(frozen=True)
class Parsed:
    """The request, the texts the door scans, and the passages once retrieved."""

    request: AskRequest
    request_id: str
    idempotency: str | None
    user_texts: dict[str, str | None]
    retrieved: Retrieved | None = None


def passage_text(passage: Passage) -> str:
    """One passage as the prompt reads it: its id, its heading path, its text."""
    path = HEADING_JOIN.join(passage.heading_path) or ABSENT
    return f"[{passage.chunk_id}] ({path})\n{passage.text}"


def passages_text(passages: list[Passage]) -> str:
    """Every passage, blank-line separated, in rank order."""
    return "\n\n".join(passage_text(p) for p in passages)


def parse(request: AskRequest, request_id: str, idempotency: str | None) -> Parsed:
    """Stage 1: the typed request becomes the pipeline's input."""
    return Parsed(request, request_id, idempotency, {"question": request.question})


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


def timeout_ms(runtime: RuntimeContext) -> int:
    """Return the per-call deadline: the settings override the descriptor."""
    return runtime.settings.capability_documents.timeout_ms or descriptor.timeout_ms


async def retrieve_passages(parsed: Parsed, runtime: RuntimeContext) -> Parsed:
    """Stage 3: the space's passages for the question, fused chunk by chunk."""
    request = parsed.request
    grounding = Grounding(
        organization_id=request.organization_id,
        spec=DOCUMENTS,
        capability=descriptor.name,
        timeout_ms=timeout_ms(runtime),
        question=request.question,
        prefix=space_prefix(request.space_id),
        kinds=tuple(request.kinds),
        k=request.k,
    )
    found = await retrieve(grounding, runtime.storage, runtime.provider)
    texts = {**parsed.user_texts, "passages": passages_text(found.passages) or None}
    return replace(parsed, retrieved=found, user_texts=texts)


def settle(parsed: Parsed, runtime: RuntimeContext) -> AskResponse | None:
    """Answer without a call when nothing worth reading came back: not found, at no cost."""
    retrieved = parsed.retrieved
    if retrieved is not None and not retrieved.found:
        runtime.budgets.settle(parsed.request.organization_id, retrieved.usage.cost_micros)
        return not_found_response(retrieved, parsed.request_id)
    return None


def assemble(parsed: Parsed, runtime: RuntimeContext) -> GenerateRequest:
    """Stage 4: the prompt file, filled; the question and the passages fenced as data."""
    request = parsed.request
    prompt = PromptFile.load(PROMPT_PATH)
    developer = fill(
        prompt.section("developer"),
        {"language": request.language or PRESERVE, "instructions": prompt.section("mode:ask")},
    )
    segments = [
        Segment(role="system", name="system", text=prompt.section("system")),
        Segment(role="developer", name="developer", text=developer),
        Segment(role="user", name="question", text=fence("question", request.question)),
        Segment(
            role="user",
            name="passages",
            text=fence("passages", parsed.user_texts.get("passages") or ABSENT),
        ),
    ]
    return GenerateRequest(
        organization_id=request.organization_id,
        request_id=parsed.request_id,
        capability=descriptor.name,
        alias=ModelAlias(descriptor.alias),
        segments=segments,
        output_schema=ask_schema(),
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
) -> tuple[AskOutput, GenerateResult]:
    """Stage 6: parse against the schema with one repair attempt; then the leakage scan."""
    output, current = await parse_with_repair(result, AskOutput, lambda: call(generate, runtime))
    texts = [text for text in parsed.user_texts.values() if text]
    refuse_if_unsafe(ask_prose(output), texts, parsed.request_id)
    return output, current


def postprocess(
    output: AskOutput, result: GenerateResult, parsed: Parsed, runtime: RuntimeContext
) -> AskResponse:
    """Stage 7: settle the spend; every claim cited, every citation a real passage."""
    retrieved = parsed.retrieved or Retrieved([], NO_USAGE, result.model_id, consulted=False)
    spent = result.usage.cost_micros + retrieved.usage.cost_micros
    runtime.budgets.settle(parsed.request.organization_id, spent)
    return to_response(output, result, retrieved, parsed.request, parsed.request_id)


def _cache_ttl(runtime: RuntimeContext) -> int:
    ttl = runtime.settings.capability_documents.cache_ttl_seconds
    return descriptor.cache_ttl_seconds if ttl is None else ttl


STAGES = Stages(
    parse=parse,
    validate=validate,
    retrieve=retrieve_passages,
    assemble=assemble,
    call=call,
    validate_output=validate_output,
    postprocess=postprocess,
    from_cache=from_cache,
    cache_ttl=_cache_ttl,
    settle=settle,
)


async def run(
    request: AskRequest, runtime: RuntimeContext, request_id: str, idempotency: str | None = None
) -> AskResponse:
    """Run the stages in order, with the cache in front of retrieval and the call."""
    return await run_stages(STAGES, request, runtime, request_id, idempotency)
