"""Prompt files: header and sections parse; filling replaces tokens and refuses unknown ones."""

from pathlib import Path

import pytest

from catalyst_ai.platform.prompts import PromptFile, fill

TEXT = "---\ncapability: x\nversion: 1\n---\n[system]\nBe brief.\n\n[developer]\nMode: {mode}\n\n[operation:clarify]\nClarify.\n"


def test_parse_header_and_sections(tmp_path: Path) -> None:
    path = tmp_path / "prompt_v1.md"
    path.write_text(TEXT, encoding="utf-8")
    prompt = PromptFile.load(path)
    assert prompt.header == {"capability": "x", "version": "1"}
    assert prompt.section("system") == "Be brief."
    assert prompt.section("operation:clarify") == "Clarify."
    with pytest.raises(KeyError):
        prompt.section("missing")


def test_missing_header_and_duplicate_section_are_defects(tmp_path: Path) -> None:
    bad = tmp_path / "prompt_v9.md"
    bad.write_text("[system]\nx\n", encoding="utf-8")
    with pytest.raises(ValueError, match="header"):
        PromptFile.load(bad)
    dup = tmp_path / "prompt_v8.md"
    dup.write_text("---\na: b\n---\n[system]\nx\n[system]\ny\n", encoding="utf-8")
    with pytest.raises(ValueError, match="twice"):
        PromptFile.load(dup)


def test_fill_replaces_tokens_and_keeps_braces_in_values() -> None:
    assert fill("Mode: {mode} {mode}", {"mode": "a {b}"}) == "Mode: a {b} a {b}"
    with pytest.raises(KeyError):
        fill("{unknown}", {})
