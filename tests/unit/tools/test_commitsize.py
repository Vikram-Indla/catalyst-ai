"""The commit-size check: one ticket, ≤ 400 hand-written lines, `gen:` generated only, no skip."""

from pathlib import Path

import pytest

from tools.checks import commitsize
from tools.checks.commitsize import Staged
from tools.checks.gitinfo import git_output

RECORD = "brain/sessions/2026-09/0-x.md"
DECIDED = "| D-900 | 2026-09-24 | lead | A size exception under RULE-005 for the split. | x |\n"
GIT_ENVIRONMENT = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR")
PROPOSED = "| D-900 | 2026-09-24 | lead (proposed) | A size exception under RULE-005. | x |\n"


def test_up_to_four_hundred_hand_written_lines_pass_and_one_more_is_refused() -> None:
    assert commitsize.check([Staged("src/catalyst_ai/a.py", 400)], {}, "") == []
    found = commitsize.check(
        [Staged("src/catalyst_ai/a.py", 300), Staged("tests/t.py", 101), Staged("x.md", 0)], {}, ""
    )
    assert [v.message for v in found] == [
        "401 hand-written lines, over 400; the biggest: src/catalyst_ai/a.py 300, tests/t.py 101, x.md 0"
    ]


def test_generated_paths_do_not_count() -> None:
    staged = [
        Staged("src/catalyst_ai/a.py", 390),
        Staged("uv.lock", 5_000),
        Staged("api/openapi.yaml", 900),
        Staged("tests/fixtures/providers/gemini/x/1.json", 700),
        Staged("docs/04-ledgers/capabilities.md", 50),
    ]
    assert commitsize.check(staged, {}, "") == []


def test_two_tickets_in_one_commit_are_refused_and_one_is_fine() -> None:
    one = {RECORD: "**Date:** x · **Ticket:** AI-031 (F-043) · **Author:** a contributor"}
    assert commitsize.check([], one, "") == []
    two = {RECORD: "**Ticket:** AI-031, AI-021 · x", "b.md": "**Ticket:** AI-031 · y"}
    found = commitsize.check([], two, "")
    assert [v.message for v in found] == ["2 tickets in one commit: AI-021, AI-031"]


def test_a_ticket_named_outside_the_ticket_field_is_not_counted() -> None:
    record = {RECORD: "**Ticket:** AI-033 · F-044 was found under AI-032's change"}
    assert commitsize.check([], record, "") == []


def test_a_gen_commit_holds_generated_paths_only() -> None:
    pure = [Staged("api/openapi.yaml", 900), Staged("tests/fixtures/providers/a/b.json", 50)]
    assert commitsize.check(pure, {}, "", "gen: contract document") == []
    mixed = [*pure, Staged("evals/x/set.jsonl", 3)]
    found = commitsize.check(mixed, {}, "", "gen(evals): sets and fixtures")
    assert [v.message for v in found] == ["a gen: commit holds the hand-written evals/x/set.jsonl"]
    assert commitsize.check(mixed, {}, "", "feat(x): y") == []


def test_only_a_decision_the_lead_took_excuses_the_size_and_it_must_be_named() -> None:
    big = [Staged("src/catalyst_ai/a.py", 900)]
    named = {RECORD: "**Ticket:** AI-035 · x\n**Size exception:** D-900\n"}
    assert commitsize.check(big, named, DECIDED) == []
    assert commitsize.check(big, named, PROPOSED) != []
    assert commitsize.check(big, {RECORD: "**Ticket:** AI-035"}, DECIDED) != []
    other_rule = DECIDED.replace("RULE-005", "RULE-001")
    assert commitsize.check(big, named, other_rule) != []


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
    found = commitsize.run(tmp_path)
    assert [v.message.split(";")[0] for v in found] == ["401 hand-written lines, over 400"]
    message = tmp_path / "MSG"
    message.write_text("gen: lockfile\n", encoding="utf-8")
    assert len(commitsize.run(tmp_path, message.read_text(encoding="utf-8").strip())) == 2
