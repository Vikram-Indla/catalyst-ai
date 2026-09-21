"""Reciprocal rank fusion of the vector and lexical legs at document level."""

import re
from dataclasses import dataclass

from catalyst_ai.contract.search import MAX_SNIPPET, Hit, Provenance
from catalyst_ai.platform.storage import StoredHit

FUSION = "rrf-k60-v1"
RRF_K = 60
LEGS = 2
WHITESPACE = re.compile(r"\s+")


@dataclass(frozen=True)
class Placed:
    """One document as a leg placed it: its rank (1-based) and the best chunk of that leg."""

    rank: int
    chunk: StoredHit


def place(hits: list[StoredHit]) -> dict[str, Placed]:
    """Collapse a leg's chunk hits to documents; the first chunk seen is the leg's best."""
    placed: dict[str, Placed] = {}
    for hit in hits:
        if hit.external_id not in placed:
            placed[hit.external_id] = Placed(len(placed) + 1, hit)
    return placed


def snippet(text: str, limit: int = MAX_SNIPPET) -> str:
    """Return the first characters of a chunk, whitespace collapsed, cut at a word when possible."""
    flat = WHITESPACE.sub(" ", text).strip()
    if len(flat) <= limit:
        return flat
    cut = flat.rfind(" ", 0, limit)
    return flat[: cut if cut > limit // 2 else limit].rstrip()


def _score(vector: Placed | None, lexical: Placed | None) -> float:
    raw = sum(1.0 / (RRF_K + placed.rank) for placed in (vector, lexical) if placed is not None)
    return round(raw / (LEGS / (RRF_K + 1)), 6)


def fuse(vector_hits: list[StoredHit], lexical_hits: list[StoredHit], k: int) -> list[Hit]:
    """Score every document by 1/(60 + rank) per leg, normalised to 1.0 for first on both legs."""
    vector = place(vector_hits)
    lexical = place(lexical_hits)
    fused: list[Hit] = []
    for external_id in sorted(set(vector) | set(lexical)):
        on_vector = vector.get(external_id)
        on_lexical = lexical.get(external_id)
        placed = on_vector if on_vector is not None else on_lexical
        if placed is None:
            continue
        best = placed.chunk
        fused.append(
            Hit(
                external_id=external_id,
                kind=best.kind,
                title=best.title,
                score=_score(on_vector, on_lexical),
                snippet=snippet(best.text),
                provenance=Provenance(
                    chunk_index=best.chunk_index,
                    embedding_model=best.embedding_model,
                    embedding_version=best.embedding_version,
                    vector_rank=on_vector.rank if on_vector else None,
                    lexical_rank=on_lexical.rank if on_lexical else None,
                    vector_similarity=round(on_vector.chunk.score, 6) if on_vector else None,
                ),
            )
        )
    fused.sort(key=lambda hit: (-hit.score, hit.external_id))
    return fused[:k]
