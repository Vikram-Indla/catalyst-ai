"""Post-processing: the confidence penalties and the cached-response rebuild."""

from catalyst_ai.capabilities.improve_story.postprocess import confidence, from_cache, to_response
from catalyst_ai.capabilities.improve_story.schema import ModelOutput
from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.providers.port import GenerateResult
from tests.unit.capabilities.improve_story.conftest import make_request


def _output(description: str, changed: bool = True) -> ModelOutput:
    return ModelOutput(
        description=description, acceptance_criteria=None, rationale="r", changed=changed
    )


def test_confidence_full_when_every_property_holds() -> None:
    request = make_request(description="see PROJ-42 and 3 items")
    assert confidence(request, _output("PROJ-42 has 3 items.")) == 1.0


def test_confidence_penalties_stack() -> None:
    request = make_request(description="see PROJ-42 and 3 items")
    assert confidence(request, _output("nothing kept")) == 0.7
    assert confidence(request, _output("x" * 200)) == 0.5
    assert confidence(request, _output("مرحبا")) == 0.2


def test_confidence_ignores_script_when_a_target_language_is_named() -> None:
    request = make_request(description="hello", language="ar")
    assert confidence(request, _output("مرحبا")) == 1.0


def test_to_response_and_from_cache() -> None:
    request = make_request()
    usage = Usage(input_tokens=1, output_tokens=1, cost_micros=9, latency_ms=8, cache_hit=False)
    result = GenerateResult(text="", model_id="m", usage=usage)
    response = to_response(_output("PROJ-42"), result, request, "r1")
    assert response.model == "text-default@m"
    cached = from_cache(response.model_dump_json(), "r2")
    assert cached.request_id == "r2"
    assert cached.usage.cache_hit is True
    assert cached.usage.cost_micros == 0
    assert cached.improved_description == "PROJ-42"
