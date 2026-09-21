"""Deterministic graders for documents (ingest): the parse matrix's indexed side."""

from collections.abc import Callable

from catalyst_ai.contract.documents import IngestRequest, IngestResponse

Grader = Callable[[IngestRequest, IngestResponse, dict[str, object]], float]


def _score(ok: bool) -> float:
    return 1.0 if ok else 0.0


def state_as_expected(
    request: IngestRequest, response: IngestResponse, expected: dict[str, object]
) -> float:
    """Indexed the first time, unchanged the second; the document id echoed."""
    return _score(
        response.state == expected.get("state") and response.document_id == request.document_id
    )


def chunks_present(
    request: IngestRequest, response: IngestResponse, expected: dict[str, object]
) -> float:
    """A parsed document yields at least one chunk and the index grew or stayed."""
    del request, expected
    return _score(response.chunks >= 1 and response.index_chunks >= response.chunks)


def headings_seen(
    request: IngestRequest, response: IngestResponse, expected: dict[str, object]
) -> float:
    """A structured format yields at least one heading; plain text yields none."""
    del expected
    if request.format.value == "text":
        return _score(response.headings == [])
    return _score(len(response.headings) >= 1)


def versions_named(
    request: IngestRequest, response: IngestResponse, expected: dict[str, object]
) -> float:
    """The embedding model and version are named on every outcome."""
    del request, expected
    return _score(bool(response.embedding_model) and response.embedding_version.startswith("d768"))


GRADERS: dict[str, Grader] = {
    "state_as_expected": state_as_expected,
    "chunks_present": chunks_present,
    "headings_seen": headings_seen,
    "versions_named": versions_named,
}
