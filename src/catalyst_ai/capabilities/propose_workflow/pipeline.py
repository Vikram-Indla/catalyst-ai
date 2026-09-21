"""The propose-workflow pipeline: parse, validate, assemble, call, validate_output, postprocess."""

from dataclasses import dataclass
from pathlib import Path

from catalyst_ai.capabilities.propose_workflow import descriptor
from catalyst_ai.capabilities.propose_workflow.postprocess import from_cache, to_response
from catalyst_ai.capabilities.propose_workflow.schema import ModelOutput, output_schema
from catalyst_ai.contract.propose_workflow import (
    ExistingStatus,
    ProposeWorkflowRequest,
    ProposeWorkflowResponse,
    Scheme,
    Transition,
)
from catalyst_ai.platform.pipeline import Door, Stages, admit, parse_with_repair, run_stages
from catalyst_ai.platform.prompts import PromptFile, fill
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.platform.safety import fence, refuse_if_unsafe
from catalyst_ai.providers.port import GenerateRequest, GenerateResult, ModelAlias, Segment

PROMPT_PATH = Path(__file__).with_name(f"prompt_v{descriptor.prompt_version}.md")
ABSENT = "(none)"
PRESERVE = "the description's own"
ANY = "*"


@dataclass(frozen=True)
class Parsed:
    """The request plus the texts the door scans and the prompt fences."""

    request: ProposeWorkflowRequest
    request_id: str
    idempotency: str | None
    user_texts: dict[str, str | None]


def _status_line(status: ExistingStatus) -> str:
    roles = (" initial" if status.initial else "") + (" terminal" if status.terminal else "")
    return f"status {status.key} [{status.category.value}] name={status.name!r}{roles}"


def _transition_line(transition: Transition) -> str:
    line = (
        f"transition {transition.from_key or ANY} -> {transition.to_key} ({transition.kind.value})"
    )
    if transition.guards:
        line += " guards=" + ",".join(transition.guards)
    if transition.reason_code:
        line += f" reason={transition.reason_code}"
    return line


def scheme_text(scheme: Scheme | None) -> str:
    """One line per status and per transition — the shape the prompt reads an existing scheme in."""
    if scheme is None:
        return ""
    lines = [_status_line(s) for s in scheme.statuses]
    lines += [_transition_line(t) for t in scheme.transitions]
    return "\n".join(lines)


def parse(request: ProposeWorkflowRequest, request_id: str, idempotency: str | None) -> Parsed:
    """Stage 1: the typed request becomes the pipeline's input; the scheme becomes one text."""
    texts: dict[str, str | None] = {
        "description": request.description,
        "existing": scheme_text(request.existing) or None,
    }
    return Parsed(request, request_id, idempotency, texts)


def validate(parsed: Parsed, runtime: RuntimeContext) -> str:
    """Stage 2: the door — switch, version, scanner, tenant cap; return the cache key."""
    door = Door(
        name=descriptor.name,
        version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        alias=descriptor.alias,
        settings=runtime.settings.capability_propose_workflow,
        organization_id=parsed.request.organization_id,
        capability_version=parsed.request.capability_version,
        user_texts=parsed.user_texts,
        canonical_input=parsed.request.model_dump(mode="json"),
        idempotency=parsed.idempotency,
    )
    return admit(door, runtime)


def assemble(parsed: Parsed, runtime: RuntimeContext) -> GenerateRequest:
    """Stage 4: the prompt file, filled; the description and the scheme fenced as data."""
    request = parsed.request
    prompt = PromptFile.load(PROMPT_PATH)
    developer = fill(
        prompt.section("developer"),
        {
            "item_type": fence("item_type", request.item_type or ABSENT),
            "categories": ", ".join(c.value for c in request.allowed_categories),
            "guards": ", ".join(request.guard_vocabulary) or ABSENT,
            "language": request.language or PRESERVE,
        },
    )
    segments = [
        Segment(role="system", name="system", text=prompt.section("system")),
        Segment(role="developer", name="developer", text=developer),
        Segment(
            role="user",
            name="description",
            text=fence("description", parsed.user_texts["description"] or ABSENT),
        ),
        Segment(
            role="user",
            name="existing",
            text=fence("existing", parsed.user_texts["existing"] or ABSENT),
        ),
    ]
    timeout = runtime.settings.capability_propose_workflow.timeout_ms or descriptor.timeout_ms
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


def prose_of(output: ModelOutput) -> str:
    """Every free-text field of a proposal, joined for the leakage scan."""
    labels = [s.name for s in output.statuses]
    rationales = [t.rationale for t in output.transitions]
    return "\n".join([*labels, *rationales, output.rationale])


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
) -> ProposeWorkflowResponse:
    """Stage 7: settle the spend; the structural check, the confidence, the response."""
    runtime.budgets.settle(parsed.request.organization_id, result.usage.cost_micros)
    return to_response(output, result, parsed.request, parsed.request_id)


def _cache_ttl(runtime: RuntimeContext) -> int:
    ttl = runtime.settings.capability_propose_workflow.cache_ttl_seconds
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
    request: ProposeWorkflowRequest,
    runtime: RuntimeContext,
    request_id: str,
    idempotency: str | None = None,
) -> ProposeWorkflowResponse:
    """Run the stages in order, with the cache in front of the call."""
    return await run_stages(STAGES, request, runtime, request_id, idempotency)
