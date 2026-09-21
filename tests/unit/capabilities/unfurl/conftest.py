"""Doubles for unfurl: request builders and well-formed completions."""

import json
from typing import Any

from catalyst_ai.contract.unfurl import UnfurlRequest
from tests.unit.capabilities.improve_story.conftest import ORG

TEXT = "The login button does nothing on small screens since the 2026-09-10 release."


def unfurl_request(**overrides: object) -> UnfurlRequest:
    values: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "kind": "item",
        "id": "item-41",
        "title": "Login button broken on mobile",
        "text": TEXT,
        "status": "in_progress",
    }
    values.update(overrides)
    return UnfurlRequest.model_validate(values)


def card_text(facts: list[dict[str, Any]] | None = None, summary: str | None = None) -> str:
    default = [
        {"label": "status", "value": "in_progress"},
        {"label": "since", "value": "2026-09-10"},
    ]
    return json.dumps(
        {
            "summary": summary or "The login button is broken on small screens.",
            "facts": default if facts is None else facts,
            "rationale": "r",
        }
    )
