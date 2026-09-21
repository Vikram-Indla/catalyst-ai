"""Embeddings through the port, batched per corpus, with the version label every row carries."""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.providers.port import EmbedRequest, Provider
from catalyst_ai.retrieval.corpora import CorpusSpec

Purpose = Literal["document", "query"]
NO_USAGE = Usage(input_tokens=0, output_tokens=0, cost_micros=0, latency_ms=0, cache_hit=False)


@dataclass(frozen=True)
class EmbedContext:
    """The tenant, the corpus, the capability and the deadline an embedding call runs under."""

    organization_id: UUID
    spec: CorpusSpec
    capability: str
    timeout_ms: int


@dataclass(frozen=True)
class Embedded:
    """Vectors in input order, the concrete model that produced them, and the usage summed."""

    vectors: list[tuple[float, ...]]
    model_id: str
    usage: Usage


def add_usage(left: Usage, right: Usage) -> Usage:
    """Sum two usages; latency adds because the calls ran one after another."""
    return Usage(
        input_tokens=left.input_tokens + right.input_tokens,
        output_tokens=left.output_tokens + right.output_tokens,
        cost_micros=left.cost_micros + right.cost_micros,
        latency_ms=left.latency_ms + right.latency_ms,
        cache_hit=left.cache_hit and right.cache_hit,
    )


async def embed_texts(
    provider: Provider, context: EmbedContext, texts: list[str], purpose: Purpose
) -> Embedded:
    """Embed the texts in batches of the corpus's size; an empty list costs nothing."""
    spec = context.spec
    vectors: list[tuple[float, ...]] = []
    usage = NO_USAGE
    model_id = provider.model_id(spec.alias)
    for start in range(0, len(texts), spec.embed_batch):
        result = await provider.embed(
            EmbedRequest(
                organization_id=context.organization_id,
                capability=context.capability,
                alias=spec.alias,
                texts=texts[start : start + spec.embed_batch],
                purpose=purpose,
                timeout_ms=context.timeout_ms,
            )
        )
        vectors.extend(tuple(vector) for vector in result.vectors)
        usage = add_usage(usage, result.usage)
        model_id = result.model_id
    return Embedded(vectors=vectors, model_id=model_id, usage=usage)
