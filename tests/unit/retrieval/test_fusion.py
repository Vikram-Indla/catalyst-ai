"""Reciprocal rank fusion: documents on both legs win, ranks and similarity travel as provenance."""

from catalyst_ai.platform.storage import StoredHit
from catalyst_ai.retrieval.fusion import FUSION, RRF_K, fuse, place, snippet


def _hit(external_id: str, score: float, chunk_index: int = 0, text: str = "t") -> StoredHit:
    return StoredHit(
        external_id, "story", "Title " + external_id, chunk_index, text, "m", "v", score
    )


def test_place_collapses_chunks_to_documents_keeping_the_first() -> None:
    placed = place([_hit("A", 0.9, 0), _hit("A", 0.8, 1), _hit("B", 0.7)])
    assert placed["A"].rank == 1
    assert placed["A"].chunk.chunk_index == 0
    assert placed["B"].rank == 2


def test_fuse_prefers_documents_found_by_both_legs() -> None:
    vector = [_hit("A", 0.9), _hit("B", 0.8), _hit("C", 0.7)]
    lexical = [_hit("C", 3.0), _hit("D", 2.0)]
    hits = fuse(vector, lexical, 10)
    assert [h.external_id for h in hits][:2] == ["C", "A"]
    first = hits[0]
    assert first.provenance.vector_rank == 3
    assert first.provenance.lexical_rank == 1
    assert first.provenance.vector_similarity == 0.7
    assert hits[-1].external_id == "D"
    assert hits[-1].provenance.vector_rank is None
    assert 0.0 < hits[-1].score < first.score <= 1.0
    assert FUSION.startswith("rrf")


def test_fuse_bounds_by_k_and_scores_first_on_both_legs_as_one() -> None:
    hits = fuse([_hit("A", 1.0), _hit("B", 0.5)], [_hit("A", 1.0)], 1)
    assert len(hits) == 1
    assert hits[0].score == 1.0
    assert RRF_K == 60
    assert fuse([], [], 5) == []


def test_snippet_collapses_whitespace_and_cuts_at_a_word() -> None:
    assert snippet("a   b\n\nc") == "a b c"
    long = " ".join(["word"] * 100)
    cut = snippet(long)
    assert len(cut) <= 240
    assert not cut.endswith(" ")
    assert snippet("x" * 300)[:240] == "x" * 240
