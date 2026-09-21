"""The propose-workflow contract: the request's rules and the shape of a scheme."""

import pytest
from pydantic import ValidationError

from catalyst_ai.capabilities.propose_workflow.postprocess import as_status, as_transition
from catalyst_ai.contract.propose_workflow import (
    ExistingStatus,
    ProposeWorkflowRequest,
    Scheme,
    StatusBase,
    StatusCategory,
    TransitionBase,
    TransitionKind,
)
from tests.unit.capabilities.propose_workflow.conftest import STATUSES, TRANSITIONS, make_request


def test_defaults_allow_every_category_and_no_guard() -> None:
    request = make_request(guard_vocabulary=[])
    assert request.allowed_categories == list(StatusCategory)
    assert request.guard_vocabulary == []
    assert request.existing is None


@pytest.mark.parametrize(
    "overrides",
    [
        {"allowed_categories": ["todo", "in_progress"]},
        {"allowed_categories": ["todo", "done", "todo"]},
        {"guard_vocabulary": ["a", "a"]},
        {"description": ""},
        {"description": "x" * 4_001},
        {"language": "English"},
    ],
)
def test_malformed_requests_are_refused(overrides: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        make_request(**overrides)


def test_a_scheme_round_trips_and_keeps_its_kinds() -> None:
    scheme = Scheme.model_validate({"statuses": STATUSES, "transitions": TRANSITIONS})
    assert scheme.transitions[2].kind is TransitionKind.BACKWARD
    assert scheme.transitions[-1].from_key is None
    request = ProposeWorkflowRequest.model_validate(
        {**make_request().model_dump(mode="json"), "existing": scheme.model_dump(mode="json")}
    )
    assert request.existing is not None
    assert len(request.existing.statuses) == 6
    with pytest.raises(ValidationError):
        Scheme.model_validate({"statuses": [{**STATUSES[0], "order": 99}], "transitions": []})


def test_an_existing_status_is_read_under_either_spelling() -> None:
    old = ExistingStatus.model_validate(
        {"key": "open", "label": "Open", "category": "todo", "sort_order": 0}
    )
    assert (old.name, old.order) == ("Open", 0)
    new = ExistingStatus.model_validate(
        {"key": "open", "name": "Open", "category": "todo", "order": 0}
    )
    assert (new.label, new.sort_order) == (None, None)
    for missing in ({"label": "Open"}, {"sort_order": 0}):
        with pytest.raises(ValidationError):
            ExistingStatus.model_validate({"key": "open", "category": "todo", **missing})
    laid_out = as_status(StatusBase.model_validate(STATUSES[0]))
    assert (laid_out.label, laid_out.sort_order) == (laid_out.name, laid_out.order)
    assert as_transition(TransitionBase.model_validate(TRANSITIONS[0])).requires_approval is False
