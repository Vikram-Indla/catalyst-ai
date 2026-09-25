"""The translation stand-in's glossary: governed terms rendered with their exact targets.

The stand-in reads the fenced glossary ("source => target", an optional note), drops the sources
it lists with two different targets (ambiguous: the capability reports them, the stand-in does
not guess either), and swaps each remaining source found in the text for a marker the script
mapping leaves alone, then puts the exact target back; a clitic the term was written onto is set
apart, so the target is a whole word in the translation. Notes are ignored, as a reviewer's text
is.
"""

import re
from collections.abc import Callable
from functools import partial

LINE = re.compile(r"^(?P<source>.+?) => (?P<target>.+?)(?: \(note: .*\))?$")
MARKER = "⁣{index}⁣"
MARKER_BACK = re.compile("⁣(\\d+)⁣")


def entries(glossary_text: str) -> list[tuple[str, str]]:
    """Return the unambiguous (source, target) pairs of the fenced glossary."""
    pairs = [
        (m.group("source").strip(), m.group("target").strip())
        for m in (LINE.match(line) for line in glossary_text.splitlines())
        if m
    ]
    targets: dict[str, set[str]] = {}
    for source, target in pairs:
        targets.setdefault(source.casefold(), set()).add(target)
    return [(s, t) for s, t in pairs if len(targets[s.casefold()]) == 1]


def _clitic_apart(match: re.Match[str], marker: str) -> str:
    """Return the marker, set apart from a clitic the term was written onto ("وبطاقة")."""
    glued = match.start() > 0 and match.string[match.start() - 1].isalpha()
    return f" {marker}" if glued else marker


def apply(text: str, glossary_text: str, convert: Callable[[str], str]) -> str:
    """Convert the text, rendering every unambiguous glossary term with its exact target."""
    pairs = sorted(entries(glossary_text), key=lambda pair: -len(pair[0]))
    targets: list[str] = []
    for source, target in pairs:
        pattern = re.compile(re.escape(source), re.I)
        if pattern.search(text):
            marker = MARKER.format(index=len(targets))
            text = pattern.sub(partial(_clitic_apart, marker=marker), text)
            targets.append(target)
    converted = convert(text)
    return MARKER_BACK.sub(lambda m: targets[int(m.group(1))], converted)
