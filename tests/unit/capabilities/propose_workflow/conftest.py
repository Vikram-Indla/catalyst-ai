"""Doubles for propose-workflow: a request builder and well-formed completions."""

import json
from typing import Any

from catalyst_ai.contract.propose_workflow import ProposeWorkflowRequest
from tests.unit.capabilities.improve_story.conftest import ORG

DESCRIPTION = (
    "A defect is reported, then triaged. Once triaged it is worked on; the developer can send it "
    "back to triage with a reason. When fixed it is verified by QA; QA can reject the fix with a "
    "reason, which sends it back to work. A verified defect is closed. A closed defect can be "
    "reopened with a reason. Any defect can be cancelled as a duplicate."
)
GUARDS = ["assignee_set", "fix_version_set", "all_subtasks_done"]


def status(
    key: str, category: str, *, initial: bool = False, terminal: bool = False, order: int = 0
) -> dict[str, Any]:
    return {
        "key": key,
        "label": key.replace("_", " ").title(),
        "category": category,
        "initial": initial,
        "terminal": terminal,
        "sort_order": order,
    }


def transition(
    from_key: str | None,
    to_key: str,
    kind: str = "forward",
    guards: list[str] | None = None,
    reason_code: str | None = None,
) -> dict[str, Any]:
    return {
        "from_key": from_key,
        "to_key": to_key,
        "kind": kind,
        "guards": guards or [],
        "requires_approval": False,
        "reason_code": reason_code,
        "rationale": f"The description implies moving to {to_key}.",
    }


STATUSES = [
    status("reported", "todo", initial=True, order=0),
    status("triaged", "todo", order=1),
    status("in_work", "in_progress", order=2),
    status("fixed", "in_progress", order=3),
    status("closed", "done", terminal=True, order=4),
    status("cancelled", "done", terminal=True, order=5),
]
TRANSITIONS = [
    transition("reported", "triaged"),
    transition("triaged", "in_work", guards=["assignee_set"]),
    transition("in_work", "triaged", "backward", reason_code="needs_triage"),
    transition("in_work", "fixed"),
    transition("fixed", "in_work", "reject", reason_code="fix_rejected"),
    transition("fixed", "closed"),
    transition("closed", "in_work", "reopen", reason_code="regression"),
    transition(None, "cancelled", "cancel"),
]


def make_request(**overrides: object) -> ProposeWorkflowRequest:
    values: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "description": DESCRIPTION,
        "item_type": "defect",
        "guard_vocabulary": GUARDS,
    }
    values.update(overrides)
    return ProposeWorkflowRequest.model_validate(values)


def proposal_text(
    statuses: list[dict[str, Any]] | None = None,
    transitions: list[dict[str, Any]] | None = None,
    empty_reason: str | None = None,
) -> str:
    return json.dumps(
        {
            "statuses": STATUSES if statuses is None else statuses,
            "transitions": TRANSITIONS if transitions is None else transitions,
            "empty_reason": empty_reason,
            "rationale": "Six statuses; the reasons the description implies are named.",
        }
    )
