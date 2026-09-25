"""The commit check: one ticket, one subject line, `gen:` generated only, no line total, no skip."""

from pathlib import Path

import pytest

from tools.checks import commitsize
from tools.checks.commitsize import Staged
from tools.checks.gitinfo import git_output

RECORD = "brain/sessions/2026-09/0-x.md"
GIT_ENVIRONMENT = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR")


def test_a_commit_has_no_total_of_lines_any_more() -> None:
    big = [Staged("src/catalyst_ai/a.py", 900), Staged("tests/t.py", 700), Staged("x.md", 0)]
    assert commitsize.check(big, {RECORD: "**Ticket:** AI-043 · x"}, "build(gate): one task") == []


def test_two_tickets_in_one_commit_are_refused_and_one_is_fine() -> None:
    one = {RECORD: "**Date:** x · **Ticket:** AI-031 (F-043) · **Author:** a contributor"}
    assert commitsize.check([], one) == []
    two = {RECORD: "**Ticket:** AI-031, AI-021 · x", "b.md": "**Ticket:** AI-031 · y"}
    found = commitsize.check([], two)
    assert [v.message for v in found] == ["2 tickets in one commit: AI-021, AI-031"]


def test_a_ticket_named_outside_the_ticket_field_is_not_counted() -> None:
    record = {RECORD: "**Ticket:** AI-033 · F-044 was found under AI-032's change"}
    assert commitsize.check([], record) == []


def test_the_message_is_one_subject_line_and_nothing_after_it() -> None:
    assert commitsize.check([], {}, "feat(x): y\n") == []
    assert commitsize.check([], {}, "feat(x): y\n# a comment git strips\n\n") == []
    found = commitsize.check([], {}, "feat(x): y\n\nA body the lead did not approve.\n")
    assert [v.message for v in found] == [
        "a commit message is one subject line; this one has 2 lines"
    ]


def test_a_gen_commit_holds_generated_paths_only() -> None:
    pure = [Staged("api/openapi.yaml", 900), Staged("tests/fixtures/providers/a/b.json", 50)]
    assert commitsize.check(pure, {}, "gen: contract document") == []
    mixed = [*pure, Staged("evals/x/set.jsonl", 3)]
    found = commitsize.check(mixed, {}, "gen(evals): sets and fixtures")
    assert [v.message for v in found] == ["a gen: commit holds the hand-written evals/x/set.jsonl"]
    assert commitsize.check(mixed, {}, "feat(x): y") == []


def test_there_is_no_flag_that_skips_the_check() -> None:
    source = Path(commitsize.__file__).read_text(encoding="utf-8")
    assert "argv[1]" not in source
    assert "argv[2]" not in source
    assert "environ" not in source
    assert "--skip" not in source


def test_the_staged_diff_is_measured_as_the_commit_will_hold_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for variable in GIT_ENVIRONMENT:
        monkeypatch.delenv(variable, raising=False)
    assert git_output(tmp_path, "init", "-q") is not None
    (tmp_path / "a.py").write_text("x = 1\n" * 401, encoding="utf-8")
    (tmp_path / "uv.lock").write_text("lock\n" * 900, encoding="utf-8")
    assert commitsize.run(tmp_path) == []
    assert git_output(tmp_path, "add", "a.py", "uv.lock") is not None
    assert commitsize.run(tmp_path) == []
    message = tmp_path / "MSG"
    message.write_text("gen: lockfile\n", encoding="utf-8")
    found = commitsize.run(tmp_path, message.read_text(encoding="utf-8"))
    assert [v.message for v in found] == ["a gen: commit holds the hand-written a.py"]
