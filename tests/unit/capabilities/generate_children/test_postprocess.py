"""The hierarchy check, de-duplication, bounding, confidence and the response."""

import pytest

from catalyst_ai.capabilities.generate_children.postprocess import (
    bound,
    candidate_confidence,
    check_hierarchy,
    expected_child_level,
    from_cache,
    mark_duplicates,
    to_response,
)
from catalyst_ai.capabilities.generate_children.schema import ModelCandidate, ModelOutput
from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.generate_children import Sibling
from catalyst_ai.platform.errors import Error
from catalyst_ai.providers.port import GenerateResult
from tests.unit.capabilities.generate_children.conftest import make_request


def _candidate(title: str, level: str = "story", duplicate_of: str | None = None) -> ModelCandidate:
    return ModelCandidate(
        type=level, title=title, description="d", acceptance_criteria=[], duplicate_of=duplicate_of
    )


def _result() -> GenerateResult:
    usage = Usage(input_tokens=1, output_tokens=1, cost_micros=9, latency_ms=8, cache_hit=False)
    return GenerateResult(text="", model_id="m", usage=usage)


def test_expected_child_level_is_the_parents_next() -> None:
    assert expected_child_level(make_request()) == "story"
    assert expected_child_level(make_request(child_level="story")) == "story"
    assert expected_child_level(make_request(parent_level="Epic")) == "story"


@pytest.mark.parametrize(
    "overrides",
    [{"child_level": "task"}, {"parent_level": "subtask"}, {"parent_level": "unknown"}],
    ids=["skips a level", "last level", "not in hierarchy"],
)
def test_level_requests_outside_the_hierarchy_are_rejected(overrides: dict[str, object]) -> None:
    with pytest.raises(Error) as caught:
        expected_child_level(make_request(**overrides))
    assert caught.value.code is ErrorCode.INPUT_REJECTED
    assert caught.value.details[0].code == "hierarchy_violation"


def test_wrong_level_candidate_refuses_the_whole_response() -> None:
    output = ModelOutput(candidates=[_candidate("a"), _candidate("b", level="task")], rationale="r")
    with pytest.raises(Error) as caught:
        check_hierarchy(output, make_request())
    assert caught.value.code is ErrorCode.OUTPUT_INVALID
    assert caught.value.details[0].code == "hierarchy_violation"
    check_hierarchy(
        ModelOutput(candidates=[_candidate("a", level="Story")], rationale="r"), make_request()
    )


def test_mark_duplicates_against_siblings_and_earlier_candidates() -> None:
    marked = mark_duplicates(
        [
            _candidate("Share a saved filter with the team"),
            _candidate("Share saved filter with team"),
            _candidate("Rotate keys"),
        ],
        ["Sharing saved filters with a team"],
    )
    assert marked[0].duplicate_of == "Sharing saved filters with a team"
    assert marked[1].duplicate_of == "Sharing saved filters with a team"
    assert marked[2].duplicate_of is None
    kept = mark_duplicates([_candidate("x", duplicate_of="Given")], [])
    assert kept[0].duplicate_of == "Given"


def test_bound_counts_only_new_candidates() -> None:
    items = [_candidate("a"), _candidate("b", duplicate_of="s"), _candidate("c"), _candidate("d")]
    kept = bound(items, 2)
    assert [c.title for c in kept] == ["a", "b", "c"]


def test_candidate_confidence_penalties() -> None:
    request = make_request()
    grounded = ModelCandidate(
        type="story",
        title="Share saved filters",
        description="with a team",
        acceptance_criteria=["g/w/t"],
    )
    assert candidate_confidence(grounded, request, "story") == 1.0
    no_criteria = grounded.model_copy(update={"acceptance_criteria": []})
    assert candidate_confidence(no_criteria, request, "story") == 0.8
    duplicate = grounded.model_copy(update={"duplicate_of": "x"})
    assert candidate_confidence(duplicate, request, "story") == 0.7
    ungrounded = grounded.model_copy(update={"title": "zzz", "description": "qqq"})
    assert candidate_confidence(ungrounded, request, "task") == 0.7


def test_to_response_marks_bounds_scores_and_reports_reason() -> None:
    request = make_request(siblings=[Sibling(title="Share saved filters with a team")], max_items=1)
    output = ModelOutput(
        candidates=[
            _candidate("Share saved filters with the team"),
            _candidate("Propagate owner changes"),
            _candidate("Unshare a filter"),
        ],
        rationale="r",
    )
    response = to_response(output, _result(), request, "rid")
    assert [c.duplicate_of is not None for c in response.candidates] == [True, False]
    assert response.empty_reason is None
    assert response.confidence is not None
    empty = to_response(
        ModelOutput(candidates=[], empty_reason="parent_too_vague", rationale="r"),
        _result(),
        request,
        "rid",
    )
    assert empty.empty_reason == "parent_too_vague"
    assert empty.confidence is None
    cached = from_cache(response.model_dump_json(), "r2")
    assert cached.usage.cache_hit is True
    assert cached.request_id == "r2"
