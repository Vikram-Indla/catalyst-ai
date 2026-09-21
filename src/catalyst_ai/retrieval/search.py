"""Hybrid search over one tenant's corpus: the vector leg, the lexical leg, the fusion."""

from dataclasses import dataclass

from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.contract.search import Hit, SearchMode
from catalyst_ai.platform.storage import SearchScope, Storage, StorageUnavailableError, StoredHit
from catalyst_ai.providers.port import Provider
from catalyst_ai.retrieval.embeddings import NO_USAGE, EmbedContext, embed_texts
from catalyst_ai.retrieval.fusion import FUSION, fuse
from catalyst_ai.retrieval.ingest import index_unavailable
from catalyst_ai.retrieval.lexical import any_query, web_query

OVERSAMPLE = 3


@dataclass(frozen=True)
class Query(EmbedContext):
    """One search as the capability hands it over."""

    mode: SearchMode
    text: str
    kinds: tuple[str, ...]
    exclude: tuple[str, ...]
    k: int


@dataclass(frozen=True)
class Found:
    """The fused hits, what the embedding cost, and the versions that ranked them."""

    hits: list[Hit]
    usage: Usage
    model_id: str
    embedding_version: str
    fusion: str = FUSION
    consulted: bool = True


async def _lexical_leg(query: Query, scope: SearchScope, storage: Storage) -> list[StoredHit]:
    lexical = any_query(query.text) if query.mode is SearchMode.SIMILAR else web_query(query.text)
    if not lexical.text:
        return []
    return await storage.search_lexical(scope, lexical)


async def search(query: Query, storage: Storage, provider: Provider) -> Found:
    """Embed the text, run both legs over the tenant's rows, fuse; an empty corpus costs nothing."""
    spec = query.spec
    model = provider.model_id(spec.alias)
    try:
        if await storage.count_chunks(query.organization_id, spec.name) == 0:
            return Found([], NO_USAGE, model, spec.version, consulted=False)
        embedded = await embed_texts(provider, query, [query.text], "query")
        scope = SearchScope(
            query.organization_id, spec.name, query.kinds, query.exclude, query.k * OVERSAMPLE
        )
        vector_hits = await storage.search_vector(
            scope, embedded.vectors[0], embedded.model_id, spec.version
        )
        lexical_hits = await _lexical_leg(query, scope, storage)
    except StorageUnavailableError as error:
        raise index_unavailable(error) from error
    return Found(
        fuse(vector_hits, lexical_hits, query.k), embedded.usage, embedded.model_id, spec.version
    )
