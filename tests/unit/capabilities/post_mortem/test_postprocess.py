"""Stage 7: facts traced and ordered, analysis evidenced, tokens only, confidence, cache."""

import pytest

from catalyst_ai.capabilities.post_mortem.postprocess import (
    confidence,
    factors_of,
    facts_of,
    from_cache,
    to_response,
)
from catalyst_ai.capabilities.post_mortem.schema import ModelOutput
from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from catalyst_ai.providers.port import GenerateResult
from tests.unit.capabilities.post_mortem.conftest import draft_text, fact, make_request

RESULT = GenerateResult(
    text="",
    model_id="double",
    usage=Usage(input_tokens=10, output_tokens=5, cost_micros=7, latency_ms=3, cache_hit=False),
)


def test_to_response_orders_facts_and_keeps_analysis_apart() -> None:
    output = ModelOutput.model_validate_json(draft_text())
    response = to_response(output, RESULT, make_request(), "rid")
    assert [f.source_id for f in response.facts] == ["ev-1", "ev-2", "ev-4"]
    assert response.contributing_factors[0].evidence == ["ev-2", "ev-3"]
    assert response.action_items[0].confidence == 0.7
    assert response.participants_mentioned == ["p2"]
    assert response.confidence == 1.0


def test_facts_are_deduplicated_and_reordered_by_the_timeline() -> None:
    output = ModelOutput.model_validate_json(
        draft_text(facts=[fact("ev-4", "last"), fact("ev-1", "first"), fact("ev-1", "again")])
    )
    facts = facts_of(output, make_request())
    assert [(f.source_id, f.text) for f in facts] == [("ev-1", "first"), ("ev-4", "last")]
    dropped = ModelOutput.model_validate_json(
        draft_text(factors=[{"text": "no evidence", "evidence": []}])
    )
    assert factors_of(dropped) == []


def test_untraceable_and_foreign_tokens_are_refused() -> None:
    bad = ModelOutput.model_validate_json(draft_text(facts=[fact("ev-9", "invented")]))
    with pytest.raises(Error) as unknown:
        to_response(bad, RESULT, make_request(), "rid")
    assert unknown.value.code is ErrorCode.OUTPUT_INVALID
    assert unknown.value.details[0].code == "untraceable_entry"
    foreign = ModelOutput.model_validate_json(draft_text(summary="p7 fixed it."))
    with pytest.raises(Error) as unsafe:
        to_response(foreign, RESULT, make_request(), "rid")
    assert unsafe.value.code is ErrorCode.OUTPUT_UNSAFE
    named = ModelOutput.model_validate_json(draft_text(mentioned=("p9",)))
    with pytest.raises(Error):
        to_response(named, RESULT, make_request(), "rid")


def test_confidence_penalties_and_empty() -> None:
    output = ModelOutput.model_validate_json(draft_text())
    full = to_response(output, RESULT, make_request(), "rid")
    assert confidence(full.facts, [], full.action_items, 4) == 0.8
    unevidenced = [full.action_items[0].model_copy(update={"evidence": []})]
    assert confidence(full.facts, full.contributing_factors, unevidenced, 4) == 0.9
    assert confidence(full.facts[:1], full.contributing_factors, full.action_items, 4) == 0.9
    empty = ModelOutput.model_validate_json(
        draft_text([], [], [], "", empty_reason="timeline_empty")
    )
    response = to_response(empty, RESULT, make_request(timeline=[]), "rid")
    assert response.empty_reason == "timeline_empty"
    assert response.facts == []
    assert response.confidence == 1.0


def test_from_cache_marks_the_hit() -> None:
    output = ModelOutput.model_validate_json(draft_text())
    first = to_response(output, RESULT, make_request(), "r1")
    again = from_cache(first.model_dump_json(), "r2")
    assert again.request_id == "r2"
    assert again.usage.cache_hit is True
    assert again.facts == first.facts
