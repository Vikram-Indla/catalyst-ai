"""Stage 7: the confidence score and the cached response."""

from catalyst_ai.capabilities.interpret_query.postprocess import confidence, from_cache
from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.contract.interpret_query import InterpretQueryResponse


def test_confidence_drops_for_unresolved_terms_and_for_an_empty_query() -> None:
    assert confidence('issuetype = "Bug"', []) == 1.0
    assert confidence('issuetype = "Bug"', ["red"]) == 0.8
    assert confidence("", ["blocked by vendors"]) == 0.4


def test_a_cached_response_is_a_free_hit_under_the_new_request_id() -> None:
    usage = Usage(input_tokens=10, output_tokens=5, cost_micros=40, latency_ms=9, cache_hit=False)
    original = InterpretQueryResponse(
        capability_version="1.0.0",
        prompt_version="1",
        model="text-fast@m",
        eval_set_version="1",
        usage=usage,
        request_id="first",
        query='issuetype = "Bug"',
        explanation="Bugs",
        unresolved=[],
        confidence=1.0,
    )
    again = from_cache(original.model_dump_json(), "second")
    assert again.request_id == "second"
    assert again.usage.cache_hit is True
    assert again.usage.cost_micros == 0
    assert again.query == original.query
