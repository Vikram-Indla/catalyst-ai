"""Doubles for generate-children: a request builder and a well-formed candidate list."""

import json

from catalyst_ai.contract.generate_children import GenerateChildrenRequest
from tests.unit.capabilities.improve_story.conftest import ORG

HIERARCHY = ["theme", "initiative", "epic", "story", "task", "subtask"]
PARENT = (
    "Members share saved filters with a team. Shared filters carry view or edit permission. "
    "A shared filter appears in the team section. Changes by the owner propagate to everyone."
)


def make_request(**overrides: object) -> GenerateChildrenRequest:
    values: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "target": "stories",
        "hierarchy": HIERARCHY,
        "parent_level": "epic",
        "parent_title": "Saved filter sharing",
        "parent_description": PARENT,
    }
    values.update(overrides)
    return GenerateChildrenRequest.model_validate(values)


def candidates_text(*titles: str, level: str = "story", duplicate_of: str | None = None) -> str:
    output = {
        "candidates": [
            {
                "type": level,
                "title": t,
                "description": f"{t}, as part of the parent.",
                "acceptance_criteria": ["Given a, when b, then c"],
                "duplicate_of": duplicate_of,
            }
            for t in titles
        ],
        "empty_reason": None,
        "rationale": "Proposed from the parent.",
    }
    return json.dumps(output)


def empty_text(reason: str) -> str:
    return json.dumps(
        {"candidates": [], "empty_reason": reason, "rationale": "Nothing to propose."}
    )
