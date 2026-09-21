"""Doubles for release-notes: a request builder and well-formed completions."""

import json
from typing import Any

from catalyst_ai.contract.release_notes import ReleaseNotesRequest
from tests.unit.capabilities.improve_story.conftest import ORG


def change(
    index: int, kind: str = "story", state: str = "done", who: str | None = None
) -> dict[str, Any]:
    return {
        "id": f"chg-{index}",
        "key": f"PRJ-{100 + index}",
        "kind": kind,
        "title": f"Change number {index} for the board export",
        "status_category": state,
        "participant": who,
    }


CHANGES = [
    change(1, "story", who="p1"),
    change(2, "bug"),
    change(3, "story", state="in_progress", who="p2"),
    change(4, "task"),
]


def make_request(**overrides: object) -> ReleaseNotesRequest:
    values: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "mode": "notes",
        "release": {"name": "Board export", "version": "2.4.0", "target_date": "2026-10-02"},
        "changes": CHANGES,
        "audience": "internal",
    }
    values.update(overrides)
    return ReleaseNotesRequest.model_validate(values)


def entry(source_id: str, text: str) -> dict[str, str]:
    return {"source_id": source_id, "text": text}


def notes_text(
    sections: list[dict[str, Any]] | None = None,
    highlights: list[dict[str, str]] | None = None,
    summary: str = "",
    attention: list[dict[str, str]] | None = None,
    empty_reason: str | None = None,
) -> str:
    default_sections = [
        {"kind": "story", "entries": [entry("chg-1", "PRJ-101: export the board (p1)")]},
        {"kind": "bug", "entries": [entry("chg-2", "PRJ-102: the fix")]},
        {"kind": "task", "entries": [entry("chg-4", "PRJ-104: build image")]},
    ]
    return json.dumps(
        {
            "sections": default_sections if sections is None else sections,
            "highlights": [entry("chg-1", "Export the board")]
            if highlights is None
            else highlights,
            "summary": summary,
            "attention": attention or [],
            "empty_reason": empty_reason,
            "rationale": "One entry per done change.",
        }
    )
