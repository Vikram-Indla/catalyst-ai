"""Doubles for post-mortem: a request builder and well-formed completions."""

import json
from typing import Any

from catalyst_ai.contract.post_mortem import PostMortemRequest
from tests.unit.capabilities.improve_story.conftest import ORG


def event(index: int, text: str, who: str | None = "p1") -> dict[str, Any]:
    return {
        "id": f"ev-{index}",
        "at": f"2026-09-14T08:{index:02d}:00+00:00",
        "participant": who,
        "text": text,
    }


TIMELINE = [
    event(1, "Alert fired: error rate above 5% on the search endpoint."),
    event(2, "Deploy 7001 identified as the last change before the alert.", "p2"),
    event(3, "Rollback of deploy 7001 started.", "p2"),
    event(4, "Rollback complete; error rate back under 1%.", None),
]


def make_request(**overrides: object) -> PostMortemRequest:
    values: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "incident": {"key": "INC-9", "title": "Search cluster degraded", "severity": "sev2"},
        "timeline": TIMELINE,
    }
    values.update(overrides)
    return PostMortemRequest.model_validate(values)


def fact(source_id: str, text: str) -> dict[str, str]:
    return {"source_id": source_id, "text": text}


def draft_text(
    facts: list[dict[str, str]] | None = None,
    factors: list[dict[str, Any]] | None = None,
    actions: list[dict[str, Any]] | None = None,
    summary: str = "The search endpoint failed after deploy 7001 and recovered on rollback.",
    **overrides: Any,
) -> str:
    mentioned = overrides.get("mentioned", ())
    empty_reason = overrides.get("empty_reason")
    default_facts = [
        fact("ev-1", "The alert fired on the search endpoint"),
        fact("ev-2", "p2 identified deploy 7001 as the last change"),
        fact("ev-4", "The rollback restored the error rate"),
    ]
    default_factors = [{"text": "A deploy preceded the failure", "evidence": ["ev-2", "ev-3"]}]
    default_actions = [
        {"text": "Add a canary step before search deploys", "evidence": ["ev-2"], "confidence": 0.7}
    ]
    return json.dumps(
        {
            "summary": summary,
            "facts": default_facts if facts is None else facts,
            "contributing_factors": default_factors if factors is None else factors,
            "action_items": default_actions if actions is None else actions,
            "participants_mentioned": list(mentioned),
            "empty_reason": empty_reason,
            "rationale": "Every fact cites its entry.",
        }
    )
