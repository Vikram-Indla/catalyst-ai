"""Embeddings through the port: batches of the corpus size, usage summed, the version label."""

import dataclasses

from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.retrieval import WORK_ITEMS
from catalyst_ai.retrieval.embeddings import NO_USAGE, EmbedContext, add_usage, embed_texts
from tests.unit.capabilities.improve_story.conftest import DOUBLE_MODEL, ScriptedProvider
from tests.unit.platform.storage.conftest import ORG_A


async def test_embed_texts_batches_by_the_corpus_size() -> None:
    provider = ScriptedProvider(["{}"])
    spec = dataclasses.replace(WORK_ITEMS, embed_batch=2)
    context = EmbedContext(ORG_A, spec, "search", 1_000)
    embedded = await embed_texts(provider, context, ["a", "b", "c"], "document")
    assert len(embedded.vectors) == 3
    assert [len(call.texts) for call in provider.embed_calls] == [2, 1]
    assert provider.embed_calls[0].purpose == "document"
    assert embedded.model_id == DOUBLE_MODEL
    assert embedded.usage.input_tokens == 3


async def test_embed_texts_of_nothing_costs_nothing() -> None:
    provider = ScriptedProvider(["{}"])
    embedded = await embed_texts(provider, EmbedContext(ORG_A, WORK_ITEMS, "s", 1), [], "query")
    assert embedded.vectors == []
    assert embedded.usage == NO_USAGE
    assert provider.embed_calls == []


def test_add_usage_sums_and_keeps_the_hit_flag_conservative() -> None:
    left = Usage(input_tokens=1, output_tokens=2, cost_micros=3, latency_ms=4, cache_hit=True)
    right = Usage(input_tokens=10, output_tokens=0, cost_micros=30, latency_ms=40, cache_hit=False)
    total = add_usage(left, right)
    assert (total.input_tokens, total.cost_micros, total.latency_ms) == (11, 33, 44)
    assert total.cache_hit is False
