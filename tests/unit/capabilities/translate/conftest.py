"""Doubles for translate: a request builder and well-formed completions."""

import json

from catalyst_ai.contract.translate import TranslateRequest
from tests.unit.capabilities.improve_story.conftest import ORG

FIELD = (
    "## Context\n\nThe login button does nothing.\n\n- open the app\n- tap `Log in`\n\nSee PRJ-42."
)
FIELD_AR = (
    "## السياق\n\nزر تسجيل الدخول لا يستجيب.\n\n- افتح التطبيق\n- انقر `Log in`\n\nانظر PRJ-42."
)


def make_request(**overrides: object) -> TranslateRequest:
    values: dict[str, object] = {
        "organization_id": ORG,
        "capability_version": "1.0.0",
        "mode": "field",
        "text": FIELD,
        "target_language": "ar",
    }
    values.update(overrides)
    return TranslateRequest.model_validate(values)


def translation_text(translated: str = FIELD_AR, detected: str = "en") -> str:
    return json.dumps(
        {"translated_text": translated, "detected_language": detected, "rationale": "Mapped."},
        ensure_ascii=False,
    )
