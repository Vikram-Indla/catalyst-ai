"""The structural validator on planted proposals: every rule names its detail."""

from catalyst_ai.capabilities.propose_workflow.scheme import (
    CATEGORY_NOT_ALLOWED,
    DUPLICATE_STATUS,
    ENDPOINT_UNKNOWN,
    EXISTING_DROPPED,
    GUARD_UNKNOWN,
    NO_INITIAL,
    NO_TERMINAL,
    REASON_MISSING,
    SELF_LOOP,
    UNREACHABLE_STATUS,
    check_scheme,
    reachable_from,
)
from catalyst_ai.contract.propose_workflow import Status, Transition
from tests.unit.capabilities.propose_workflow.conftest import (
    STATUSES,
    TRANSITIONS,
    make_request,
    status,
    transition,
)


def _codes(statuses: list[dict[str, object]], transitions: list[dict[str, object]]) -> list[str]:
    details = check_scheme(
        [Status.model_validate(s) for s in statuses],
        [Transition.model_validate(t) for t in transitions],
        make_request(),
    )
    return [d.code for d in details]


def test_the_well_formed_proposal_passes() -> None:
    assert _codes(STATUSES, TRANSITIONS) == []


def test_zero_or_two_initials_and_an_initial_outside_todo_are_no_initial() -> None:
    none = [{**s, "initial": False} for s in STATUSES]
    assert NO_INITIAL in _codes(none, TRANSITIONS)
    two = [{**s, "initial": s["key"] in {"reported", "triaged"}} for s in STATUSES]
    assert NO_INITIAL in _codes(two, TRANSITIONS)
    wrong = [{**s, "category": "in_progress" if s["initial"] else s["category"]} for s in STATUSES]
    codes = _codes(wrong, TRANSITIONS)
    assert NO_INITIAL in codes
    assert UNREACHABLE_STATUS not in codes


def test_no_terminal_in_done_is_refused() -> None:
    open_ended = [{**s, "terminal": False} for s in STATUSES]
    assert NO_TERMINAL in _codes(open_ended, TRANSITIONS)


def test_unreachable_status_is_named() -> None:
    statuses = [*STATUSES, status("parked", "todo", order=6)]
    codes = _codes(statuses, TRANSITIONS)
    assert codes == [UNREACHABLE_STATUS]
    reached = reachable_from(
        "reported",
        {s["key"] for s in statuses},
        [Transition.model_validate(t) for t in TRANSITIONS],
    )
    assert "parked" not in reached
    assert "cancelled" in reached


def test_a_null_from_key_reaches_every_status() -> None:
    statuses = [*STATUSES, status("parked", "in_progress", order=6)]
    transitions = [*TRANSITIONS, transition(None, "parked", "defer")]
    assert _codes(statuses, transitions) == []


def test_endpoints_self_loops_guards_and_reasons() -> None:
    transitions = [
        *TRANSITIONS,
        transition("triaged", "nowhere"),
        transition("fixed", "fixed"),
        transition("triaged", "in_work", guards=["moon_phase"]),
        transition("closed", "triaged", "backward"),
    ]
    codes = _codes(STATUSES, transitions)
    assert codes.count(ENDPOINT_UNKNOWN) == 1
    assert codes.count(SELF_LOOP) == 1
    assert codes.count(GUARD_UNKNOWN) == 1
    assert codes.count(REASON_MISSING) == 1


def test_duplicate_keys_and_disallowed_categories() -> None:
    statuses = [*STATUSES, status("closed", "done", terminal=True, order=9)]
    assert DUPLICATE_STATUS in _codes(statuses, TRANSITIONS)
    request = make_request(allowed_categories=["todo", "done"])
    details = check_scheme(
        [Status.model_validate(s) for s in STATUSES],
        [Transition.model_validate(t) for t in TRANSITIONS],
        request,
    )
    assert [d.message for d in details if d.code == CATEGORY_NOT_ALLOWED] == ["in_work", "fixed"]


def test_an_existing_status_may_not_be_dropped() -> None:
    existing = {"statuses": [*STATUSES, status("on_hold", "todo", order=7)], "transitions": []}
    details = check_scheme(
        [Status.model_validate(s) for s in STATUSES],
        [Transition.model_validate(t) for t in TRANSITIONS],
        make_request(existing=existing),
    )
    assert [(d.code, d.message) for d in details] == [(EXISTING_DROPPED, "on_hold")]
