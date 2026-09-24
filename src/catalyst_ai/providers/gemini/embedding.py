"""The regional provider's embedding call: the predict body, and the vectors read back.

One request carries every text as an instance with its task type; the parameters fix the
dimensions. The response carries a vector per instance and, per vector, the tokens it counted,
which price the call when present (the character estimate stands in when they are not).
"""

import math
from types import MappingProxyType
from typing import Any

from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.providers.gemini import errors
from catalyst_ai.providers.gemini.models import ModelSpec
from catalyst_ai.providers.port import EmbedRequest, EmbedResult

EMBED_METHOD = "predict"
EMBED_TASKS = MappingProxyType({"document": "RETRIEVAL_DOCUMENT", "query": "RETRIEVAL_QUERY"})
EMBED_DIMENSIONS = 768
SHAPE_NO_EMBEDDINGS = "no embeddings in the response"
SHAPE_WRONG_SIZE = "an embedding of the wrong size"


def build_embed_body(request: EmbedRequest) -> dict[str, Any]:
    """Build the predict body: one instance per text with its task type, and the dimensions."""
    task = EMBED_TASKS[request.purpose]
    return {
        "instances": [{"content": text, "task_type": task} for text in request.texts],
        "parameters": {"outputDimensionality": EMBED_DIMENSIONS},
    }


def normalise(vector: list[float]) -> list[float]:
    """Scale to unit length; the provider's reduced-dimension vectors are not normalised."""
    norm = math.sqrt(sum(value * value for value in vector))
    return [value / norm for value in vector] if norm else vector


def _vector(prediction: object, request_id: str) -> tuple[list[float], int]:
    embeddings = prediction.get("embeddings") if isinstance(prediction, dict) else None
    values = embeddings.get("values") if isinstance(embeddings, dict) else None
    if not isinstance(values, list) or len(values) != EMBED_DIMENSIONS:
        raise errors.from_shape(SHAPE_WRONG_SIZE, request_id)
    statistics = embeddings.get("statistics") if isinstance(embeddings, dict) else None
    counted = statistics.get("token_count", 0) if isinstance(statistics, dict) else 0
    return normalise([float(v) for v in values]), int(counted)


def parse_embed(
    payload: dict[str, Any], spec: ModelSpec, estimate: int, latency_ms: int, request_id: str
) -> EmbedResult:
    """Read the vectors back; price the call by the tokens counted, else by the estimate."""
    predictions = payload.get("predictions")
    if not isinstance(predictions, list) or not predictions:
        raise errors.from_shape(SHAPE_NO_EMBEDDINGS, request_id)
    read = [_vector(prediction, request_id) for prediction in predictions]
    tokens = sum(counted for _, counted in read) or estimate
    usage = Usage(
        input_tokens=tokens,
        output_tokens=0,
        cost_micros=spec.cost_micros(tokens, 0),
        latency_ms=latency_ms,
        cache_hit=False,
    )
    return EmbedResult(vectors=[vector for vector, _ in read], model_id=spec.model_id, usage=usage)
