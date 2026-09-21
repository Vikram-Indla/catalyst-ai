"""Stage 7: the structural refusal, the confidence signals, the empty proposal, the cache copy."""

import pytest

from catalyst_ai.capabilities.propose_workflow.postprocess import (
    confidence,
    dead_ends,
    from_cache,
    to_response,
)
from catalyst_ai.capabilities.propose_workflow.schema import ModelOutput
from catalyst_ai.contract.envelopes import Usage
from catalyst_ai.contract.errors import ErrorCode
from catalyst_ai.contract.propose_workflow import Status, Transition
from catalyst_ai.platform.errors import Error
from catalyst_ai.providers.port import GenerateResult
from tests.unit.capabilities.propose_workflow.conftest import (
    STATUSES,
    TRANSITIONS,
    make_request,
    proposal_text,
    status,
    transition,
)

RESULT = GenerateResult(
    text="",
    model_id="double",
    usage=Usage(input_tokens=10, output_tokens=5, cost_micros=7, latency_ms=3, cache_hit=False),
)


def _statuses(raw: list[dict[str, object]]) -> list[Status]:
    return [Status.model_validate(s) for s in raw]


def _transitions(raw: list[dict[str, object]]) -> list[Transition]:
    return [Transition.model_validate(t) for t in raw]


def test_to_response_carries_the_scheme_and_full_confidence() -> None:
    output = ModelOutput.model_validate_json(proposal_text())
    response = to_response(output, RESULT, make_request(), "rid")
    assert [s.key for s in response.statuses] == [s["key"] for s in STATUSES]
    assert len(response.transitions) == len(TRANSITIONS)
    assert response.empty_reason is None
    assert response.confidence == 1.0
    assert response.usage.cost_micros == 7


def test_an_invalid_scheme_is_output_invalid_with_every_detail() -> None:
    statuses = [*STATUSES, status("parked", "todo", order=6)]
    transitions = [*TRANSITIONS, transition("triaged", "in_work", guards=["moon_phase"])]
    output = ModelOutput.model_validate_json(proposal_text(statuses, transitions))
    with pytest.raises(Error) as caught:
        to_response(output, RESULT, make_request(), "rid")
    assert caught.value.code is ErrorCode.OUTPUT_INVALID
    assert {d.code for d in caught.value.details} == {
        "workflow_guard_unknown",
        "workflow_unreachable_status",
    }


def test_an_empty_proposal_carries_the_reason_and_nothing_else() -> None:
    output = ModelOutput.model_validate_json(proposal_text([], [], "description_too_vague"))
    response = to_response(output, RESULT, make_request(description="hello"), "rid")
    assert response.statuses == []
    assert response.transitions == []
    assert response.empty_reason == "description_too_vague"
    assert response.confidence == 1.0


def test_confidence_penalises_size_dead_ends_and_no_progress() -> None:
    assert confidence(_statuses(STATUSES), _transitions(TRANSITIONS)) == 1.0
    stuck = _transitions([t for t in TRANSITIONS if t["from_key"] not in {"fixed", None}])
    assert dead_ends(_statuses(STATUSES), stuck) == ["fixed"]
    assert confidence(_statuses(STATUSES), stuck) == 0.9
    assert dead_ends(_statuses(STATUSES), _transitions(TRANSITIONS)) == []
    flat = _statuses(
        [
            status("open", "todo", initial=True),
            status("done", "done", terminal=True, order=1),
        ]
    )
    assert confidence(flat, _transitions([transition("open", "done")])) == 0.9
    big = _statuses([*STATUSES, *(status(f"s{i}", "in_progress", order=i) for i in range(6, 14))])
    assert confidence(big, _transitions([transition(None, "closed")])) == 0.9


def test_from_cache_marks_the_hit_and_renames_the_request() -> None:
    output = ModelOutput.model_validate_json(proposal_text())
    first = to_response(output, RESULT, make_request(), "r1")
    again = from_cache(first.model_dump_json(), "r2")
    assert again.request_id == "r2"
    assert again.usage.cache_hit is True
    assert again.usage.cost_micros == 0
    assert again.statuses == first.statuses
