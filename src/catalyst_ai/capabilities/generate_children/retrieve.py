"""Stage 3: the tenant's index names the existing children the request's siblings did not."""

from catalyst_ai.capabilities.generate_children import descriptor
from catalyst_ai.contract.generate_children import GenerateChildrenRequest
from catalyst_ai.contract.search import SearchMode
from catalyst_ai.platform.runtime import RuntimeContext
from catalyst_ai.retrieval import WORK_ITEMS, Query, search

INDEXED_SIBLINGS_K = 30


async def indexed_siblings(
    request: GenerateChildrenRequest, child_level: str, runtime: RuntimeContext
) -> tuple[str, ...] | None:
    """Titles of indexed items at the child level near the parent; None when nothing is indexed."""
    if not runtime.settings.capability_search.enabled:
        return None
    query = Query(
        organization_id=request.organization_id,
        spec=WORK_ITEMS,
        capability=descriptor.name,
        timeout_ms=runtime.settings.capability_generate_children.timeout_ms
        or descriptor.timeout_ms,
        mode=SearchMode.SIMILAR,
        text=f"{request.parent_title}\n\n{request.parent_description}",
        kinds=(child_level.lower(),),
        exclude=tuple(s.key for s in request.siblings if s.key),
        k=INDEXED_SIBLINGS_K,
    )
    found = await search(query, runtime.storage, runtime.provider)
    if not found.consulted:
        return None
    return tuple(hit.title or hit.snippet for hit in found.hits)
