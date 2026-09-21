"""Deterministic retrieval graders: recall@10, MRR, tenant isolation, provenance, filters, inertness."""

from collections.abc import Callable

from catalyst_ai.contract.search import SearchRequest, SearchResponse

Grader = Callable[[SearchRequest, SearchResponse, dict[str, object]], float]
K = 10


def _score(ok: bool) -> float:
    return 1.0 if ok else 0.0


def _relevant(expected: dict[str, object]) -> list[str]:
    value = expected.get("relevant")
    return [str(v) for v in value] if isinstance(value, list) else []


def _ids(response: SearchResponse) -> list[str]:
    return [hit.external_id for hit in response.hits]


def recall_at_10(
    request: SearchRequest, response: SearchResponse, expected: dict[str, object]
) -> float:
    """Share of the relevant items among the first ten hits; 1.0 when nothing is labelled."""
    del request
    relevant = _relevant(expected)
    if not relevant:
        return 1.0
    top = set(_ids(response)[:K])
    return len([r for r in relevant if r in top]) / len(relevant)


def mrr(request: SearchRequest, response: SearchResponse, expected: dict[str, object]) -> float:
    """Reciprocal rank of the first relevant hit; 1.0 when nothing is labelled."""
    del request
    relevant = set(_relevant(expected))
    if not relevant:
        return 1.0
    for rank, external_id in enumerate(_ids(response), start=1):
        if external_id in relevant:
            return 1.0 / rank
    return 0.0


def tenant_isolation(
    request: SearchRequest, response: SearchResponse, expected: dict[str, object]
) -> float:
    """No hit is one of the case's forbidden keys (another organisation's copies)."""
    del request
    forbidden = expected.get("forbidden")
    banned = {str(v) for v in forbidden} if isinstance(forbidden, list) else set()
    return _score(not banned & set(_ids(response)))


def provenance_present(
    request: SearchRequest, response: SearchResponse, expected: dict[str, object]
) -> float:
    """Every hit names its embedding model and version and at least one leg's rank."""
    del request, expected
    return _score(
        all(
            hit.provenance.embedding_model
            and hit.provenance.embedding_version
            and (hit.provenance.vector_rank or hit.provenance.lexical_rank)
            for hit in response.hits
        )
    )


def kinds_respected(
    request: SearchRequest, response: SearchResponse, expected: dict[str, object]
) -> float:
    """When the request filters by kind, every hit is of those kinds."""
    del expected
    return _score(not request.kinds or all(hit.kind in request.kinds for hit in response.hits))


def injection_inert(
    request: SearchRequest, response: SearchResponse, expected: dict[str, object]
) -> float:
    """An instruction in the query is data: the response is a normal, tenant-only hit list."""
    del request
    if not expected.get("inert"):
        return 1.0
    return _score(
        tenant_isolation(SearchRequest.model_construct(), response, expected) == 1.0
        and response.hits is not None
        and response.embedding_version != ""
    )


GRADERS: dict[str, Grader] = {
    "recall_at_10": recall_at_10,
    "mrr": mrr,
    "tenant_isolation": tenant_isolation,
    "provenance_present": provenance_present,
    "kinds_respected": kinds_respected,
    "injection_inert": injection_inert,
}
