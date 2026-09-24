"""The predict body and its reading: one instance per text, unit vectors, tokens as counted."""

from uuid import uuid4

import pytest

from catalyst_ai.platform.errors import Error
from catalyst_ai.providers.gemini.embedding import (
    EMBED_DIMENSIONS,
    build_embed_body,
    normalise,
    parse_embed,
)
from catalyst_ai.providers.gemini.models import EMBEDDING
from catalyst_ai.providers.port import EmbedRequest, ModelAlias


def _prediction(counted: int | None = None) -> dict[str, object]:
    embeddings: dict[str, object] = {"values": [3.0, 4.0] + [0.0] * (EMBED_DIMENSIONS - 2)}
    if counted is not None:
        embeddings["statistics"] = {"token_count": counted}
    return {"embeddings": embeddings}


def test_documents_and_queries_carry_their_task_type() -> None:
    request = EmbedRequest(
        organization_id=uuid4(),
        capability="c",
        alias=ModelAlias.EMBED_DEFAULT,
        texts=["a"],
        purpose="document",
        timeout_ms=1000,
    )
    body = build_embed_body(request)
    assert body["instances"] == [{"content": "a", "task_type": "RETRIEVAL_DOCUMENT"}]


def test_vectors_come_back_unit_length_and_priced_by_the_counted_tokens() -> None:
    payload = {"predictions": [_prediction(5), _prediction(6)]}
    result = parse_embed(payload, EMBEDDING, estimate=99, latency_ms=1, request_id="r")
    assert result.vectors[0][:2] == [0.6, 0.8]
    assert result.usage.input_tokens == 11
    assert result.usage.cost_micros == EMBEDDING.cost_micros(11, 0)


def test_the_estimate_prices_the_call_when_nothing_was_counted() -> None:
    result = parse_embed(
        {"predictions": [_prediction()]}, EMBEDDING, estimate=9, latency_ms=1, request_id="r"
    )
    assert result.usage.input_tokens == 9


@pytest.mark.parametrize(
    "payload",
    [{}, {"predictions": []}, {"predictions": [{"embeddings": {"values": [1.0]}}]}],
    ids=["none", "empty", "wrong size"],
)
def test_a_malformed_response_is_refused(payload: dict[str, object]) -> None:
    with pytest.raises(Error):
        parse_embed(payload, EMBEDDING, estimate=1, latency_ms=1, request_id="r")


def test_a_zero_vector_is_left_as_it_is() -> None:
    assert normalise([0.0, 0.0]) == [0.0, 0.0]
