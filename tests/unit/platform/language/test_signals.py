"""The shared signals: identifiers, links, facts, digits, length ratio, dominant script."""

from catalyst_ai.platform.language import (
    dominant_script,
    identifiers,
    identifiers_preserved,
    latin,
    length_ratio,
    links,
    script_preserved,
    stated_facts,
)


def test_identifiers_and_preservation() -> None:
    assert identifiers("See PRJ-42 and 3.5 items on build 4100") == {"PRJ-42", "3.5", "4100"}
    assert identifiers_preserved("PRJ-42", "fixed PRJ-42 today") is True
    assert identifiers_preserved("PRJ-42", "fixed PRJ-43") is False


def test_length_ratio_and_scripts() -> None:
    assert length_ratio("abcd", "ab") == 0.5
    assert length_ratio("", "ab") == 2.0
    assert dominant_script("hello") == "LATIN"
    assert dominant_script("مرحبا") == "ARABIC"
    assert dominant_script("123") == "LATIN"
    assert script_preserved("hello", "world") is True
    assert script_preserved("hello", "مرحبا") is False


def test_a_link_ends_where_its_sentence_does() -> None:
    assert links("See https://a.example/x. Or https://b.example/y, or https://c.example/z؟") == {
        "https://a.example/x",
        "https://b.example/y",
        "https://c.example/z",
    }
    assert links(
        "قدّم عبر https://a.example/x، ثم https://b.example/y؛ ثم https://c.example/z۔"
    ) == {
        "https://a.example/x",
        "https://b.example/y",
        "https://c.example/z",
    }


def test_a_closing_bracket_belongs_to_a_link_only_when_the_link_opened_it() -> None:
    assert links("Read https://w.example/wiki/Mercury_(planet).") == {
        "https://w.example/wiki/Mercury_(planet)"
    }
    assert links("(see https://a.example/x) and [docs](https://b.example/y).") == {
        "https://a.example/x",
        "https://b.example/y",
    }
    assert links("<https://a.example/x>") == {"https://a.example/x"}


def test_digits_and_facts_read_as_latin() -> None:
    assert latin("٤٠٪ و۷۰") == "40٪ و70"
    assert stated_facts("PRJ-7 from ٤٠ to 70, https://a.example/x.") == {
        "PRJ-7",
        "40",
        "70",
        "https://a.example/x",
    }
