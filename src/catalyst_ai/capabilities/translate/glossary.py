"""The glossary rule: a governed term found in the text is rendered with its exact target.

Matching tolerates what a language does to a term without changing it: case in Latin script, and
in Arabic the diacritics, the tatweel, the forms of alef and the clitics a word takes (a term
inside "وبطاقة المشروع" is still "بطاقة المشروع", and "للمحور" is "ل" and "المحور"). A term is a
whole word or words: it matches neither inside a longer Latin word ("Period" is not in "periodic")
nor as a part of a longer term the text names ("Objective" is not checked inside "Project
Objective"), and a Latin term is found in its plural. A source the glossary lists with two
different targets is ambiguous: it is reported and never enforced, since picking one would be a
guess.
"""

import re
from typing import Final

from catalyst_ai.contract.translate import GlossaryConflict, GlossaryEntry

DIACRITICS = re.compile(r"[ً-ْٰـ]")
ALEFS = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ى": "ي"})
SPACES = re.compile(r"\s+")
CONTRACTED_ARTICLE = re.compile(r"(^|[\sو])لل")
CONSUMED = " \x00 "
AMBIGUOUS: Final = "ambiguous_glossary"
NOT_RENDERED: Final = "term_not_rendered"


def normalise(text: str) -> str:
    """Return the text as terms are compared: casefolded, Arabic marks and alef forms unified."""
    unified = SPACES.sub(" ", DIACRITICS.sub("", text).translate(ALEFS)).casefold()
    return CONTRACTED_ARTICLE.sub(r"\1لال", unified)


def _pattern(normalised_term: str) -> re.Pattern[str]:
    return re.compile(rf"(?<![a-z0-9]){re.escape(normalised_term)}(?:e?s)?(?![a-z0-9])")


def contains(text: str, term: str) -> bool:
    """Return whether the term occurs in the text as a whole word, as the glossary compares them."""
    return _pattern(normalise(term)).search(normalise(text)) is not None


def named(glossary: list[GlossaryEntry], text: str) -> set[str]:
    """Return the normalised sources the text names, the longest first, none inside another."""
    remaining = normalise(text)
    found: set[str] = set()
    for key in sorted({normalise(entry.source) for entry in glossary}, key=len, reverse=True):
        pattern = _pattern(key)
        if pattern.search(remaining):
            found.add(key)
            remaining = pattern.sub(CONSUMED, remaining)
    return found


def ambiguous_sources(glossary: list[GlossaryEntry]) -> set[str]:
    """Return the sources the glossary gives more than one target, normalised."""
    targets: dict[str, set[str]] = {}
    for entry in glossary:
        targets.setdefault(normalise(entry.source), set()).add(normalise(entry.target))
    return {source for source, found in targets.items() if len(found) > 1}


def render(glossary: list[GlossaryEntry]) -> str:
    """Return the glossary one term per line, as the model reads it; notes are data too."""
    lines = []
    for entry in glossary:
        note = f" (note: {entry.note})" if entry.note else ""
        lines.append(f"{entry.source} => {entry.target}{note}")
    return "\n".join(lines)


def enforce(
    glossary: list[GlossaryEntry], source_text: str, translated: str
) -> tuple[list[str], list[GlossaryConflict]]:
    """Return the terms enforced and the conflicts: ambiguous, or found but not rendered."""
    ambiguous = ambiguous_sources(glossary)
    applied: list[str] = []
    conflicts: list[GlossaryConflict] = []
    seen: set[str] = set()
    in_text = named(glossary, source_text)
    for entry in glossary:
        key = normalise(entry.source)
        if key in seen or key not in in_text:
            continue
        seen.add(key)
        if key in ambiguous:
            conflicts.append(GlossaryConflict(source=entry.source, reason=AMBIGUOUS))
        elif contains(translated, entry.target):
            applied.append(entry.source)
        else:
            conflicts.append(GlossaryConflict(source=entry.source, reason=NOT_RENDERED))
    return applied, conflicts
