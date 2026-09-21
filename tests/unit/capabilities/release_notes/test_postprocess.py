"""Stage 7: traceability, tokens, sections in the changes' order, in-flight, confidence, cache."""

import pytest

from catalyst_ai.capabilities.release_notes.postprocess import (
    confidence,
    from_cache,
    in_flight,
    sections_of,
    to_response,
)
from catalyst_ai.capabilities.release_notes.schema import ModelOutput
from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from catalyst_ai.providers.port import GenerateResult
from tests.unit.capabilities.release_notes.conftest import entry, make_request, notes_text

RESULT = GenerateResult(
    text="",
    model_id="double",
    usage=Usage(input_tokens=10, output_tokens=5, cost_micros=7, latency_ms=3, cache_hit=False),
)


def test_to_response_orders_sections_by_the_changes_and_lists_in_flight() -> None:
    output = ModelOutput.model_validate_json(notes_text())
    response = to_response(output, RESULT, make_request(), "rid")
    assert [s.kind for s in response.sections] == ["story", "bug", "task"]
    assert response.sections[0].entries[0].source_id == "chg-1"
    assert response.in_flight == ["chg-3"]
    assert response.highlights[0].source_id == "chg-1"
    assert response.empty_reason is None
    assert response.confidence == 1.0


def test_an_entry_citing_an_unknown_change_is_output_invalid() -> None:
    sections = [{"kind": "story", "entries": [entry("chg-99", "invented")]}]
    output = ModelOutput.model_validate_json(notes_text(sections=sections, highlights=[]))
    with pytest.raises(Error) as caught:
        to_response(output, RESULT, make_request(), "rid")
    assert caught.value.code is ErrorCode.OUTPUT_INVALID
    assert caught.value.details[0].code == "untraceable_entry"
    assert caught.value.details[0].message == "chg-99"


def test_a_token_outside_the_changes_is_output_unsafe() -> None:
    sections = [{"kind": "story", "entries": [entry("chg-1", "done by p7")]}]
    output = ModelOutput.model_validate_json(notes_text(sections=sections, highlights=[]))
    with pytest.raises(Error) as caught:
        to_response(output, RESULT, make_request(), "rid")
    assert caught.value.code is ErrorCode.OUTPUT_UNSAFE


def test_empty_and_confidence_penalties() -> None:
    empty = ModelOutput.model_validate_json(notes_text([], [], empty_reason="nothing_to_report"))
    response = to_response(empty, RESULT, make_request(), "rid")
    assert response.empty_reason == "nothing_to_report"
    assert response.sections == []
    assert response.in_flight == ["chg-3"]
    partial = ModelOutput.model_validate_json(
        notes_text(sections=[{"kind": "story", "entries": [entry("chg-1", "x")]}], highlights=[])
    )
    sections = sections_of(partial, make_request())
    assert [s.kind for s in sections] == ["story"]
    assert confidence(sections, [], make_request()) == 0.7
    assert confidence(sections, [], make_request(mode="summary")) == 1.0
    assert in_flight(make_request(changes=[])) == []


def test_from_cache_marks_the_hit() -> None:
    output = ModelOutput.model_validate_json(notes_text())
    first = to_response(output, RESULT, make_request(), "r1")
    again = from_cache(first.model_dump_json(), "r2")
    assert again.request_id == "r2"
    assert again.usage.cache_hit is True
    assert again.sections == first.sections
