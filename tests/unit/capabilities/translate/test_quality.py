"""The deterministic signals: scripts, detection, the Markdown skeleton, the kept spans."""

from catalyst_ai.capabilities.translate.quality import (
    detect_language,
    in_target_script,
    kept_spans,
    script_for,
    skeleton,
    structure_preserved,
)
from tests.unit.capabilities.translate.conftest import FIELD, FIELD_AR


def test_scripts_and_detection() -> None:
    assert script_for("ar") == "ARABIC"
    assert script_for("en-GB") == "LATIN"
    assert script_for("fr") == "LATIN"
    assert detect_language(FIELD) == "en"
    assert detect_language(FIELD_AR) == "ar"
    assert detect_language("123") == "und"
    assert in_target_script(FIELD_AR, "ar") is True
    assert in_target_script(FIELD, "ar") is False
    assert in_target_script("PRJ-42 `code` https://x.y", "ar") is True


def test_skeleton_and_kept_spans() -> None:
    assert skeleton(FIELD) == ["h2", "", "p", "", "li", "li", "", "p"]
    assert skeleton("| a | b |\n| - | - |\n```\nx\n```") == ["tr3", "tr3", "```", "```"]
    assert kept_spans(FIELD) == ["PRJ-42", "`Log in`"]
    assert kept_spans("{{ name }} ${var} {min} %s https://a.b/c") == [
        "${var}",
        "%s",
        "https://a.b/c",
        "{min}",
        "{{ name }}",
    ]


def test_structure_preserved() -> None:
    assert structure_preserved(FIELD, FIELD_AR) is True
    assert structure_preserved(FIELD, FIELD_AR.replace("- ", "")) is False
    assert structure_preserved(FIELD, FIELD_AR.replace("PRJ-42", "PRJ-43")) is False
