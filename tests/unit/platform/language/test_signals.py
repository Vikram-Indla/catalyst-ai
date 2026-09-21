"""The shared signals: identifiers, length ratio, dominant script."""

from catalyst_ai.platform.language import (
    dominant_script,
    identifiers,
    identifiers_preserved,
    length_ratio,
    script_preserved,
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
