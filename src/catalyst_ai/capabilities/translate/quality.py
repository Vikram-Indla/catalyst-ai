"""Deterministic signals for translations: the script of a language, the Markdown skeleton."""

import re
import unicodedata
from types import MappingProxyType

from catalyst_ai.platform.language import dominant_script

SCRIPT_OF_LANGUAGE = MappingProxyType(
    {
        "ar": "ARABIC",
        "fa": "ARABIC",
        "ur": "ARABIC",
        "he": "HEBREW",
        "ru": "CYRILLIC",
        "uk": "CYRILLIC",
        "el": "GREEK",
        "zh": "CJK",
        "ja": "CJK",
        "ko": "HANGUL",
        "hi": "DEVANAGARI",
    }
)
LATIN = "LATIN"
UNDETERMINED = "und"
TARGET_SHARE = 0.8
LANGUAGE_OF_SCRIPT = MappingProxyType(
    {"ARABIC": "ar", "HEBREW": "he", "CYRILLIC": "ru", "GREEK": "el", "LATIN": "en"}
)
HEADING = re.compile(r"^(\s{0,3}#{1,6})\s", re.M)
LIST_MARKER = re.compile(r"^(\s*)([-*+]|\d+[.)])\s", re.M)
FENCE = re.compile(r"```[^\n]*\n.*?```", re.S)
INLINE_CODE = re.compile(r"`[^`\n]+`")
URL = re.compile(r"https?://[^\s)>\]]+")
PLACEHOLDER = re.compile(r"\{\{[^}]*\}\}|\$\{[^}]*\}|\{[A-Za-z_][A-Za-z0-9_]*\}|%[sd]")
KEY = re.compile(r"\b[A-Z][A-Z0-9]{1,9}-\d{1,7}\b")


def script_for(language: str) -> str:
    """Return the script a language tag is written in; Latin unless the table says otherwise."""
    return SCRIPT_OF_LANGUAGE.get(language.split("-", maxsplit=1)[0].lower(), LATIN)


def detect_language(text: str) -> str:
    """Detect coarsely by dominant script: enough to tell the source apart from the target."""
    if not any(c.isalpha() for c in text):
        return UNDETERMINED
    return LANGUAGE_OF_SCRIPT.get(dominant_script(text), UNDETERMINED)


def in_target_script(text: str, target: str) -> bool:
    """Whether the letters of a translation are mostly in the target language's script."""
    letters = [c for c in _without_kept_spans(text) if c.isalpha()]
    if not letters:
        return True
    wanted = script_for(target)
    matching = sum(1 for c in letters if unicodedata.name(c, "").split(" ")[0] == wanted)
    return matching / len(letters) >= TARGET_SHARE


def kept_spans(text: str) -> list[str]:
    """Return what must survive untouched: fences, inline code, links, placeholders, keys."""
    return sorted(
        FENCE.findall(text)
        + INLINE_CODE.findall(text)
        + URL.findall(text)
        + PLACEHOLDER.findall(text)
        + KEY.findall(text)
    )


def _without_kept_spans(text: str) -> str:
    stripped = FENCE.sub(" ", text)
    stripped = INLINE_CODE.sub(" ", stripped)
    stripped = URL.sub(" ", stripped)
    stripped = KEY.sub(" ", stripped)
    return PLACEHOLDER.sub(" ", stripped)


def skeleton(text: str) -> list[str]:
    """Return the Markdown skeleton: one entry per line — heading, list marker, row, or `p`."""
    lines = []
    for line in FENCE.sub("```\n```", text).split("\n"):
        if not line.strip():
            lines.append("")
        elif HEADING.match(line):
            lines.append("h" + str(len(line.lstrip().split(" ")[0])))
        elif LIST_MARKER.match(line):
            lines.append("li")
        elif line.startswith("|"):
            lines.append("tr" + str(line.count("|")))
        elif line.strip() == "```":
            lines.append("```")
        else:
            lines.append("p")
    return lines


def structure_preserved(source: str, result: str) -> bool:
    """Whether the skeleton and every kept span survive."""
    return skeleton(source) == skeleton(result) and set(kept_spans(source)) <= set(
        kept_spans(result)
    )
