"""A chain shaped like the one the backend sends, and a model answer that rests on it."""

import json
from uuid import UUID

from catalyst_ai.contract.brief import BriefRequest

ORG = UUID("11111111-1111-7111-8111-111111111111")
CHAIN: dict[str, object] = {
    "theme": {"id": "T-1", "title": "Digital services", "charter_summary": "Move services online."},
    "objectives": [
        {
            "id": "O-1",
            "title": "Online renewal",
            "status": "at_risk",
            "progress": 35,
            "key_results": [
                {"id": "KR-1", "title": "Online share", "value": 42, "target": 80, "unit": "%"},
                {"id": "KR-2", "title": "Satisfaction", "value": None, "target": 4.5},
            ],
        }
    ],
    "projects": [
        {
            "id": "P-1",
            "title": "Portal rebuild",
            "delivery_health": "off_track",
            "strategic_health": "on_track",
            "blocked": True,
        }
    ],
    "findings": [{"id": "F-1", "text": "The contract expires early.", "severity": "high"}],
}


def brief_request(**overrides: object) -> BriefRequest:
    values: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "chain": CHAIN,
        "locale": "en",
    }
    values.update(overrides)
    return BriefRequest.model_validate(values)


def answer(**overrides: object) -> str:
    body: dict[str, object] = {
        "summary": [
            {
                "text": "Online renewal has strategic status at risk, at 35% progress.",
                "cites": ["O-1"],
            },
            {
                "text": "Portal rebuild: delivery health off track, strategic health on track.",
                "cites": ["P-1"],
            },
        ],
        "highlights": [],
        "risks": [{"text": "Portal rebuild is blocked.", "cites": ["P-1"]}],
        "asks": [{"text": "Set a measurement for Satisfaction.", "cites": ["KR-2"]}],
        "unsupported": [],
        "empty_reason": None,
        "rationale": "From the chain.",
    }
    body.update(overrides)
    return json.dumps(body)
