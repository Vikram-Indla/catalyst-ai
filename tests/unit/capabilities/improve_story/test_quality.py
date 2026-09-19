"""Quality signals: identifiers, length ratio, scripts, Given/When/Then."""

from catalyst_ai.capabilities.improve_story.quality import (
    dominant_script,
    has_given_when_then,
    identifiers,
    identifiers_preserved,
    length_ratio,
    script_preserved,
)


def test_identifiers_include_keys_and_numbers_once() -> None:
    assert identifiers("PROJ-42 blocks PROJ-57, limit 250, timeout 30s, v4.2.") == {
        "PROJ-42",
        "PROJ-57",
        "250",
        "30",
        "4.2",
    }


def test_identifiers_preserved() -> None:
    assert identifiers_preserved("see PROJ-1 and 3 items", "3 items depend on PROJ-1.")
    assert not identifiers_preserved("see PROJ-1", "see nothing")


def test_length_ratio_handles_empty_source() -> None:
    assert length_ratio("", "ab") == 2.0
    assert length_ratio("abcd", "ab") == 0.5


def test_scripts() -> None:
    assert dominant_script("hello") == "LATIN"
    assert dominant_script("مرحبا") == "ARABIC"
    assert dominant_script("123") == "LATIN"
    assert script_preserved("hello", "bonjour")
    assert not script_preserved("hello", "مرحبا")


def test_given_when_then() -> None:
    assert has_given_when_then("- Given a, when b, then c")
    assert not has_given_when_then("a then b")
    assert not has_given_when_then(None)
