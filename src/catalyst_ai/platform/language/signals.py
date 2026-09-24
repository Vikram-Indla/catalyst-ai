"""Deterministic text signals every capability may share: identifiers, length, script."""

import re
import unicodedata
from types import MappingProxyType

ITEM_KEY = re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d{1,7}\b")
NUMBER = re.compile(r"(?<![\d.])\d+(?:[.,]\d+)?(?!\d)")
LATIN = "LATIN"
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
LINK = re.compile(r"https?://[^\s<>\"]+")
TRAILING = ".,;:!?'*،؛؟۔"
OPENERS = MappingProxyType({")": "(", "]": "["})


def latin(text: str) -> str:
    """Return the text with every Arabic-Indic or Persian digit written as a Latin one."""
    return text.translate(DIGITS)


def _trimmed(link: str) -> str:
    """Return the link without the sentence punctuation or unbalanced closing bracket after it."""
    while link and (
        link[-1] in TRAILING
        or (link[-1] in OPENERS and link.count(OPENERS[link[-1]]) < link.count(link[-1]))
    ):
        link = link[:-1]
    return link


def links(text: str) -> set[str]:
    """Return every link the text carries, as written, whatever punctuation closes its sentence.

    A full stop, a comma, a colon, `!`, `?`, `'`, `*` and the Arabic `،` `؛` `؟` `۔` right after a
    link end the sentence, not the link; a closing bracket belongs to the link only when the link
    opened it (`…/Mercury_(planet)`), so `(see …/a)` and `[text](…/a)` read `…/a`.
    """
    return {_trimmed(found) for found in LINK.findall(text)}


def identifiers(text: str) -> set[str]:
    """Item keys and numbers a text carries; a rewrite must keep every one of them."""
    keys = set(ITEM_KEY.findall(text))
    return keys | set(NUMBER.findall(ITEM_KEY.sub(" ", text)))


def stated_facts(text: str) -> set[str]:
    """Every number, item key and link a text states, its digits read as Latin."""
    plain = latin(text)
    return identifiers(plain) | links(plain)


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
