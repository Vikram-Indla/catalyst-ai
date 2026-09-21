"""Doubles for summarize: a request builder and well-formed completions."""

import json
from typing import Any

from catalyst_ai.contract.summarize import SummarizeRequest
from tests.unit.capabilities.improve_story.conftest import ORG

AT = "2026-09-01T09:00:00+00:00"


def item(index: int, text: str, participant: str = "p1") -> dict[str, object]:
    return {"id": f"c{index}", "participant": participant, "at": AT, "text": text}


THREAD = [
    item(1, "I looked at the export flow; the last step fails.", "p1"),
    item(2, "We decided to ship it behind a flag. See PRJ-42.", "p2"),
    item(3, "Blocked: the environment is missing the setting.", "p3"),
    item(4, "Can someone confirm the numbers include archived items?", "p1"),
]


def make_request(**overrides: object) -> SummarizeRequest:
    values: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "mode": "comments",
        "items": THREAD,
        "item_title": "Export the board to CSV",
        "item_type": "Story",
        "target_words": 120,
    }
    values.update(overrides)
    return SummarizeRequest.model_validate(values)


def summary_text(
    summary: str = "p1 found the last export step failing; p2 decided to ship it behind a flag.\n\n"
    "- p3 — blocker: the environment is missing the setting.\n- p1 — open question: archived items?",
    mentioned: tuple[str, ...] = ("p1", "p2", "p3"),
    empty_reason: str | None = None,
    standup: list[dict[str, Any]] | None = None,
    digest: list[dict[str, Any]] | None = None,
) -> str:
    return json.dumps(
        {
            "summary": summary,
            "participants_mentioned": list(mentioned),
            "empty_reason": empty_reason,
            "rationale": "Kept the decision, the blocker and the question.",
            "standup": standup or [],
            "digest": digest or [],
        }
    )
