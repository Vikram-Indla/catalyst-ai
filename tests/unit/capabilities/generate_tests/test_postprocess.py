"""Stage 7: traceability, the bound, the gaps, the artefacts, confidence, cache."""

import pytest

from catalyst_ai.capabilities.generate_tests.postprocess import (
    cases_of,
    confidence,
    from_cache,
    gaps_of,
    to_response,
)
from catalyst_ai.capabilities.generate_tests.schema import ModelOutput
from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.platform.errors import Error
from catalyst_ai.providers.port import GenerateResult
from tests.unit.capabilities.generate_tests.conftest import (
    CASES,
    EXISTING,
    OUTLINE,
    TABLES,
    case,
    cases_text,
    make_request,
)

RESULT = GenerateResult(
    text="",
    model_id="double",
    usage=Usage(input_tokens=10, output_tokens=5, cost_micros=7, latency_ms=3, cache_hit=False),
)


def test_to_response_keeps_cases_and_computes_gaps() -> None:
    output = ModelOutput.model_validate_json(cases_text())
    response = to_response(output, RESULT, make_request(), "rid")
    assert [c.covers for c in response.cases] == [["ac-1"], ["ac-2"], ["ac-3"]]
    assert response.gaps == []
    assert response.confidence == 1.0
    fewer = ModelOutput.model_validate_json(cases_text(CASES[:1]))
    partial = to_response(fewer, RESULT, make_request(), "rid")
    assert partial.gaps == ["ac-2", "ac-3"]
    assert partial.confidence == 0.8


def test_the_bound_and_the_inferred_penalty() -> None:
    many = [case(f"Case {i}", ["ac-1"], "happy") for i in range(8)]
    output = ModelOutput.model_validate_json(cases_text(many))
    response = to_response(output, RESULT, make_request(max_cases=3), "rid")
    assert len(response.cases) == 3
    assert response.confidence == 0.7
    inferred = [*CASES, case("Verify end to end", [], "integration", inferred=True)]
    kept = cases_of(ModelOutput.model_validate_json(cases_text(inferred)), make_request())
    assert confidence(kept, [], make_request()) == 0.9
    assert gaps_of([], make_request(criteria=[])) == []


def test_an_untraceable_or_uncited_case_is_output_invalid() -> None:
    bad = ModelOutput.model_validate_json(cases_text([case("x", ["ac-9"])]))
    with pytest.raises(Error) as unknown:
        to_response(bad, RESULT, make_request(), "rid")
    assert unknown.value.code is ErrorCode.OUTPUT_INVALID
    assert unknown.value.details[0].code == "untraceable_entry"
    bare = ModelOutput.model_validate_json(cases_text([case("x", [])]))
    with pytest.raises(Error) as uncited:
        to_response(bare, RESULT, make_request(), "rid")
    assert uncited.value.details[0].message == "no criterion and not inferred"


def test_artefacts_are_cleaned_and_traced() -> None:
    output = ModelOutput.model_validate_json(cases_text([], OUTLINE, TABLES))
    request = make_request(mode="artefacts", criteria=[], cases=EXISTING)
    response = to_response(output, RESULT, request, "rid")
    assert response.cases == []
    assert [s.heading for s in response.outline] == ["Scope"]
    assert response.data_tables[0].covers == ["tc-1"]
    assert response.confidence == 1.0
    bad_tables = [{**TABLES[0], "covers": ["tc-9"]}]
    broken = ModelOutput.model_validate_json(cases_text([], OUTLINE, bad_tables))
    with pytest.raises(Error) as caught:
        to_response(broken, RESULT, request, "r")
    assert caught.value.details[0].field == "data_tables.0"


def test_empty_and_cache() -> None:
    empty = ModelOutput.model_validate_json(cases_text([], empty_reason="nothing_to_test"))
    response = to_response(empty, RESULT, make_request(), "rid")
    assert response.empty_reason == "nothing_to_test"
    assert response.cases == []
    again = from_cache(response.model_dump_json(), "r2")
    assert again.request_id == "r2"
    assert again.usage.cache_hit is True
