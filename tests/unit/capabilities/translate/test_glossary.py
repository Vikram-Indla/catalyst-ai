"""The glossary rule: exact targets enforced, Arabic forms tolerated, ambiguity reported, not guessed."""

from catalyst_ai.capabilities.translate.glossary import (
    ambiguous_sources,
    contains,
    enforce,
    normalise,
    render,
)
from catalyst_ai.contract.translate import GlossaryEntry

CARD = GlossaryEntry(source="Project Card", target="بطاقة المشروع")
THEME_A = GlossaryEntry(source="Theme", target="المحور")
THEME_B = GlossaryEntry(source="theme", target="الموضوع")
NOTED = GlossaryEntry(source="Charter", target="الميثاق", note="the governing document")


def test_matching_tolerates_case_diacritics_alef_forms_and_clitics() -> None:
    assert contains("The PROJECT CARD is ready", "Project Card")
    assert contains("وبطاقة المشروع جاهزة", "بطاقة المشروع")
    assert contains("أُطلق المحور", "اطلق المحور")
    assert normalise("  A\tB ") == " a b "


def test_a_source_with_two_targets_is_ambiguous_whatever_its_case() -> None:
    assert ambiguous_sources([THEME_A, THEME_B, CARD]) == {"theme"}


def test_the_glossary_is_rendered_one_term_per_line_with_its_note_as_data() -> None:
    assert render([CARD, NOTED]) == (
        "Project Card => بطاقة المشروع\nCharter => الميثاق (note: the governing document)"
    )


def test_enforced_terms_are_named_and_the_rest_reported_never_guessed() -> None:
    text = "Each Theme has one Charter and one Project Card."
    translated = "لكل محور ميثاق واحد و بطاقة المشروع واحدة."
    applied, conflicts = enforce([THEME_A, THEME_B, NOTED, CARD], text, translated)
    assert applied == ["Project Card"]
    assert [(c.source, c.reason) for c in conflicts] == [
        ("Theme", "ambiguous_glossary"),
        ("Charter", "term_not_rendered"),
    ]


def test_a_term_absent_from_the_text_is_neither_applied_nor_reported() -> None:
    assert enforce([CARD], "Nothing governed here.", "لا شيء") == ([], [])
