"""The response of a turn: confidence, the cache rebuild, the row."""

from catalyst_ai.capabilities.assistant.reply import confidence, from_cache, to_response
from catalyst_ai.capabilities.assistant.schema import Output, Tail
from catalyst_ai.capabilities.assistant.sources import Source
from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.providers.port import GenerateResult
from tests.unit.capabilities.assistant.conftest import turn_request

USAGE = Usage(input_tokens=10, output_tokens=5, cost_micros=7, latency_ms=3, cache_hit=False)
RESULT = GenerateResult(text="", model_id="double", usage=USAGE)
SOURCES = [Source(1, "item", "item-41", "story APP-41: Login")]


def test_confidence_rewards_cited_sources_and_trusts_a_not_found() -> None:
    found = Tail(not_found=False, rationale="r")
    assert confidence("Broken. [1]", found, SOURCES) == 1.0
    assert confidence("Broken.", found, SOURCES) == 0.9
    assert confidence("Broken.", found, []) == 0.8
    assert confidence("Nothing here.", Tail(not_found=True, rationale="r"), []) == 1.0


def test_to_response_and_from_cache() -> None:
    output = Output("The button is broken on mobile. [1]", Tail(rationale="r"))
    response = to_response(output, RESULT, SOURCES, turn_request(), "r1")
    assert response.reply == output.prose
    assert [(s.marker, s.kind, s.source_id) for s in response.sources] == [(1, "item", "item-41")]
    assert response.model == "text-default@double"
    again = from_cache(response.model_dump_json(), "r2")
    assert again.request_id == "r2"
    assert again.usage.cache_hit is True
    assert again.usage.cost_micros == 0
