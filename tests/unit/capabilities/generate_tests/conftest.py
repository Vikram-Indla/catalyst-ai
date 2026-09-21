"""Doubles for generate-tests: a request builder and well-formed completions."""

import json
from typing import Any

from catalyst_ai.contract.generate_tests import GenerateTestsRequest
from tests.unit.capabilities.improve_story.conftest import ORG

CRITERIA = [
    {"id": "ac-1", "text": "Every visible column is exported"},
    {"id": "ac-2", "text": "Archived items stay out of the export"},
    {"id": "ac-3", "text": "A member without the permission sees no export button"},
]
EXISTING = [
    {
        "id": "tc-1",
        "title": "Verify every visible column is exported",
        "objective": "Columns",
        "steps": [{"action": "Export the board", "expected": "The file has every column"}],
    },
    {"id": "tc-2", "title": "Verify archived items stay out", "steps": []},
]


def make_request(**overrides: object) -> GenerateTestsRequest:
    values: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "mode": "cases",
        "story": {"key": "PRJ-7", "title": "Export the board to CSV", "description": "As a lead"},
        "criteria": CRITERIA,
        "max_cases": 5,
    }
    values.update(overrides)
    return GenerateTestsRequest.model_validate(values)


def case(
    title: str, covers: list[str], area: str = "happy", *, inferred: bool = False
) -> dict[str, Any]:
    return {
        "title": title,
        "given": "A signed-in lead on the board",
        "when": "The export runs",
        "then": "The outcome holds",
        "priority": "high",
        "area": area,
        "covers": covers,
        "inferred": inferred,
    }


CASES = [
    case("Verify every column", ["ac-1"]),
    case("Verify archived items stay out", ["ac-2"], "negative"),
    case("Verify the permission gate", ["ac-3"], "security"),
]
OUTLINE = [{"heading": "Scope", "lines": ["The two cases"], "covers": ["tc-1", "tc-2"]}]
TABLES = [
    {"name": "Columns", "columns": ["variant", "value"], "rows": [["a", "1"]], "covers": ["tc-1"]}
]


def cases_text(
    cases: list[dict[str, Any]] | None = None,
    outline: list[dict[str, Any]] | None = None,
    tables: list[dict[str, Any]] | None = None,
    empty_reason: str | None = None,
) -> str:
    return json.dumps(
        {
            "cases": CASES if cases is None else cases,
            "gaps": [],
            "outline": outline or [],
            "data_tables": tables or [],
            "empty_reason": empty_reason,
            "rationale": "One case per criterion.",
        }
    )
