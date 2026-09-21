"""Passages for a question: both legs over one space's windows, fused chunk by chunk."""

from dataclasses import dataclass

from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.platform.storage import SearchScope, Storage, StorageUnavailableError, StoredHit
from catalyst_ai.providers.port import Provider
from catalyst_ai.retrieval.documents import Passage, passage_of
from catalyst_ai.retrieval.embeddings import NO_USAGE, EmbedContext, embed_texts
from catalyst_ai.retrieval.fusion import LEGS, RRF_K
from catalyst_ai.retrieval.ingest import index_unavailable
from catalyst_ai.retrieval.lexical import web_query

OVERSAMPLE = 3
SCORE_FLOOR = 0.15


@dataclass(frozen=True)
class Grounding(EmbedContext):
    """One question as the capability hands it over: the space, the kinds, how many passages."""

    question: str
    prefix: str
    kinds: tuple[str, ...]
    k: int


@dataclass(frozen=True)
class Retrieved:
    """The passages in rank order, what the embedding cost, and whether the index took part."""

    passages: list[Passage]
    usage: Usage
    model_id: str
    consulted: bool = True

    @property
    def found(self) -> bool:
        """Whether anything worth reading came back: a passage at or above the floor."""
        return any(p.score >= SCORE_FLOOR for p in self.passages)


def _key(hit: StoredHit) -> tuple[str, int]:
    return hit.external_id, hit.chunk_index


def fuse_chunks(
    vector_hits: list[StoredHit], lexical_hits: list[StoredHit], k: int
) -> list[Passage]:
    """Reciprocal rank fusion per chunk; the best of both legs first, ties by key."""
    scores: dict[tuple[str, int], float] = {}
    hits: dict[tuple[str, int], StoredHit] = {}
    for leg in (vector_hits, lexical_hits):
        for rank, hit in enumerate(leg, start=1):
            scores[_key(hit)] = scores.get(_key(hit), 0.0) + 1.0 / (RRF_K + rank)
            hits.setdefault(_key(hit), hit)
    ordered = sorted(scores, key=lambda key: (-scores[key], key))
    return [
        passage_of(key[0], key[1], hits[key].text, round(scores[key] / (LEGS / (RRF_K + 1)), 6))
        for key in ordered[:k]
    ]


async def retrieve(grounding: Grounding, storage: Storage, provider: Provider) -> Retrieved:
    """Embed the question, run both legs inside the space, fuse; an empty space costs nothing."""
    spec = grounding.spec
    model = provider.model_id(spec.alias)
    try:
        if await storage.count_chunks(grounding.organization_id, spec.name) == 0:
            return Retrieved([], NO_USAGE, model, consulted=False)
        embedded = await embed_texts(provider, grounding, [grounding.question], "query")
        scope = SearchScope(
            grounding.organization_id,
            spec.name,
            grounding.kinds,
            (),
            grounding.k * OVERSAMPLE,
            grounding.prefix,
        )
        vector_hits = await storage.search_vector(
            scope, embedded.vectors[0], embedded.model_id, spec.version
        )
        lexical = web_query(grounding.question)
        lexical_hits = await storage.search_lexical(scope, lexical) if lexical.text else []
    except StorageUnavailableError as error:
        raise index_unavailable(error) from error
    return Retrieved(
        fuse_chunks(vector_hits, lexical_hits, grounding.k), embedded.usage, embedded.model_id
    )
