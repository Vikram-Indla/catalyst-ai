"""Stage 7 of unfurl: only carried facts, the confidence, the cache rebuild."""

from catalyst_ai.capabilities.unfurl.postprocess import carried, confidence, from_cache, kept_facts
from catalyst_ai.capabilities.unfurl.schema import ModelOutput
from tests.unit.capabilities.unfurl.conftest import card_text, unfurl_request

CACHED = (
    '{"capability_version":"1.0.0","prompt_version":"1","model":"m","eval_set_version":"1",'
    '"usage":{"input_tokens":1,"output_tokens":1,"cost_micros":3,"latency_ms":1,'
    '"cache_hit":false},"request_id":"r0","title":"t","summary":"s","facts":[],'
    '"confidence":1.0}'
)


def test_carried_facts_are_kept_and_the_rest_dropped() -> None:
    request = unfurl_request()
    assert carried("in_progress", request)
    assert carried("2026-09-10 release", request)
    assert not carried("the platform team", request)
    output = ModelOutput.model_validate_json(
        card_text(
            [{"label": " status ", "value": " in_progress "}, {"label": "owner", "value": "nobody"}]
        )
    )
    facts = kept_facts(output, request)
    assert [(f.label, f.value) for f in facts] == [("status", "in_progress")]
    assert confidence(output, facts, request) == 0.85
    assert confidence(output, facts, unfurl_request(text=None)) == 0.75


def test_from_cache_marks_the_hit() -> None:
    again = from_cache(CACHED, "r2")
    assert again.request_id == "r2"
    assert again.usage.cache_hit is True
    assert again.usage.cost_micros == 0
