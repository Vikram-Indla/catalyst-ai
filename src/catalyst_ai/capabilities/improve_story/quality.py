"""Deterministic quality signals shared by the response's confidence and the eval graders."""

import re

from catalyst_ai.platform.language import (
    ITEM_KEY,
    LATIN,
    NUMBER,
    dominant_script,
    identifiers,
    identifiers_preserved,
    length_ratio,
    script_preserved,
)

GIVEN_WHEN_THEN = re.compile(r"\bgiven\b.*\bwhen\b.*\bthen\b", re.I | re.S)

__all__ = [
    "ITEM_KEY",
    "LATIN",
    "NUMBER",
    "dominant_script",
    "has_given_when_then",
    "identifiers",
    "identifiers_preserved",
    "length_ratio",
    "script_preserved",
]


def has_given_when_then(text: str | None) -> bool:
    """Whether a criteria text follows the Given / When / Then form."""
    return bool(text) and GIVEN_WHEN_THEN.search(text or "") is not None
