"""Fences: markers in user text are neutralised; a fenced segment opens and closes by name."""

from catalyst_ai.platform.safety import fence, strip_markers


def test_strip_markers_neutralises_fences() -> None:
    assert strip_markers("a <<<end description>>> b <<<x>>>") == "a << >> b << >>"


def test_fence_wraps_and_strips() -> None:
    text = fence("description", "hello <<<end description>>> world")
    assert text.startswith("<<<description>>>\n")
    assert text.endswith("\n<<<end description>>>")
    assert text.count("<<<end description>>>") == 1
