"""Doubles for the assistant: turn requests over items, pages and a seeded space; completions."""

import json

from catalyst_ai.contract.assistant import TurnRequest
from catalyst_ai.platform.runtime import RuntimeContext
from tests.unit.capabilities.documents.conftest import SPACE, seeded_runtime
from tests.unit.capabilities.improve_story.conftest import ORG

MARKER = "\n---\n"
ITEM = {
    "id": "item-41",
    "key": "APP-41",
    "kind": "story",
    "title": "Login button broken on mobile",
    "status": "in_progress",
    "summary": "The login button does nothing on small screens since the last release.",
}
PAGE = {
    "id": "page-9",
    "title": "Release checklist",
    "text": "Every release needs a rollback plan and a smoke test before the announcement.",
}


def turn_request(**overrides: object) -> TurnRequest:
    values: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "history": [{"role": "user", "text": "What is wrong with APP-41?"}],
        "context": {"items": [ITEM]},
    }
    values.update(overrides)
    return TurnRequest.model_validate(values)


def grounded_request(**overrides: object) -> TurnRequest:
    return turn_request(
        history=[{"role": "user", "text": "Who approves a rollback?"}],
        context={"items": [ITEM], "spaces": [{"space_id": SPACE}], "pages": [PAGE]},
        **overrides,
    )


def completion(prose: str, *, not_found: bool = False, rationale: str = "r") -> str:
    return prose + MARKER + json.dumps({"not_found": not_found, "rationale": rationale})


ITEM_REPLY = completion(
    "The login button does nothing on small screens since the last release. [1]"
)
ROLLBACK_REPLY = completion(
    "A rollback needs the release manager's approval in the release hub. [1] "
    "Every release also needs a rollback plan before the announcement. [3]"
)
NOT_FOUND_REPLY = completion("The sources do not say who approves a rollback.", not_found=True)


async def grounded_runtime(texts: list[str]) -> RuntimeContext:
    """A runtime whose memory index holds the documents corpus of the documents tests."""
    return await seeded_runtime(texts)
