"""Deterministic quality signals shared by the response's confidence and the eval graders."""

import re
import unicodedata

ITEM_KEY = re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d{1,7}\b")
NUMBER = re.compile(r"(?<![\d.])\d+(?:[.,]\d+)?(?!\d)")
GIVEN_WHEN_THEN = re.compile(r"\bgiven\b.*\bwhen\b.*\bthen\b", re.I | re.S)
LATIN = "LATIN"


def identifiers(text: str) -> set[str]:
    """Item keys and numbers a text carries; a rewrite must keep every one of them."""
    keys = set(ITEM_KEY.findall(text))
    return keys | set(NUMBER.findall(ITEM_KEY.sub(" ", text)))


def identifiers_preserved(source: str, result: str) -> bool:
    """Whether every identifier of the source survives in the result."""
    return identifiers(source) <= identifiers(result)


def length_ratio(source: str, result: str) -> float:
    """Return result length over source length; an empty source counts as one character."""
    return len(result) / max(1, len(source))


def dominant_script(text: str) -> str:
    """Return the Unicode script most letters belong to; LATIN for an empty text."""
    counts: dict[str, int] = {}
    for char in text:
        if char.isalpha():
            script = unicodedata.name(char, "").split(" ")[0]
            counts[script] = counts.get(script, 0) + 1
    return max(counts, key=lambda s: counts[s]) if counts else LATIN


def script_preserved(source: str, result: str) -> bool:
    """Whether the result is written in the same script as the source."""
    return dominant_script(source) == dominant_script(result)


def has_given_when_then(text: str | None) -> bool:
    """Whether a criteria text follows the Given / When / Then form."""
    return bool(text) and GIVEN_WHEN_THEN.search(text or "") is not None
