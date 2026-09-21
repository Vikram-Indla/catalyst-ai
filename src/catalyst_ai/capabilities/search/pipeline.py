"""The search pipeline: parse, validate, retrieve, postprocess — no prompt, no generation."""

from dataclasses import dataclass

from catalyst_ai.capabilities.search import descriptor
from catalyst_ai.capabilities.search.postprocess import to_response
from catalyst_ai.contract.search import SearchRequest, SearchResponse
from catalyst_ai.platform.pipeline import Door, admit
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.retrieval import Found, Query, search, spec_of


@dataclass(frozen=True)
class Parsed:
    """The request and the text the door scans."""

    request: SearchRequest
    request_id: str
    user_texts: dict[str, str | None]


def parse(request: SearchRequest, request_id: str) -> Parsed:
    """Stage 1: the typed request becomes the pipeline's input value."""
    return Parsed(request, request_id, {"text": request.text})


def validate(parsed: Parsed, runtime: RuntimeContext) -> str:
    """Stage 2: the door — switch, version, scanner, tenant cap."""
    door = Door(
        name=descriptor.name,
        version=descriptor.version,
        prompt_version=descriptor.prompt_version,
        alias=descriptor.alias,
        settings=runtime.settings.capability_search,
        organization_id=parsed.request.organization_id,
        capability_version=parsed.request.capability_version,
        user_texts=parsed.user_texts,
        canonical_input=parsed.request.model_dump(mode="json"),
        idempotency=None,
    )
    return admit(door, runtime)


def timeout_ms(runtime: RuntimeContext) -> int:
    """Return the per-call deadline: the settings override the descriptor."""
    return runtime.settings.capability_search.timeout_ms or descriptor.timeout_ms


async def retrieve(parsed: Parsed, runtime: RuntimeContext) -> Found:
    """Stage 3: both legs over the tenant's corpus, fused; the embedding goes through the port."""
    request = parsed.request
    query = Query(
        organization_id=request.organization_id,
        spec=spec_of(request.corpus),
        capability=descriptor.name,
        timeout_ms=timeout_ms(runtime),
        mode=request.mode,
        text=request.text,
        kinds=tuple(request.kinds),
        exclude=tuple(request.exclude_external_ids),
        k=request.k,
    )
    return await search(query, runtime.storage, runtime.provider)


def postprocess(found: Found, parsed: Parsed) -> SearchResponse:
    """Stage 7: the response model with the versions, the usage row logged."""
    return to_response(found, parsed.request, parsed.request_id)


async def run(request: SearchRequest, runtime: RuntimeContext, request_id: str) -> SearchResponse:
    """Run the stages in order."""
    parsed = parse(request, request_id)
    validate(parsed, runtime)
    found = await retrieve(parsed, runtime)
    return postprocess(found, parsed)
