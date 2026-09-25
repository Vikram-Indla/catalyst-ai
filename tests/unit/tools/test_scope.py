"""The commit-time scope: a violation in a staged file is caught, an unchanged file is not re-read,
and a change to the ground every check stands on runs every file."""

from pathlib import Path

import pytest

from tools import precommit
from tools.checks.gate import PER_FILE, SCOPE, run_check
from tools.checks.gitinfo import git_output
from tools.scope import needs_full, partly_staged, reason, scope_of, staged

GIT_ENVIRONMENT = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR")
LONG = "".join(f"value_{n} = {n}\n" for n in range(320))


def plant(root: Path) -> tuple[Path, Path]:
    code = root / "src" / "catalyst_ai"
    code.mkdir(parents=True)
    changed, untouched = code / "changed.py", code / "untouched.py"
    changed.write_text(LONG, encoding="utf-8")
    untouched.write_text(LONG, encoding="utf-8")
    return changed, untouched


def test_a_per_file_check_reads_only_the_scope(tmp_path: Path) -> None:
    changed, _ = plant(tmp_path)
    everywhere = run_check("filebudget", tmp_path)
    scoped = run_check("filebudget", tmp_path, frozenset({changed.resolve()}))
    assert len(everywhere) == 2
    assert [v.path for v in scoped] == ["src/catalyst_ai/changed.py"]
    assert SCOPE.get() is None


def test_a_cross_file_check_always_reads_the_whole_repository() -> None:
    assert "dupl" not in PER_FILE
    assert "structure" not in PER_FILE
    assert {"filebudget", "vocabulary", "comments"} <= PER_FILE


@pytest.mark.parametrize(
    ("paths", "full"),
    [
        ([], True),
        (["src/catalyst_ai/capabilities/brief/pipeline.py"], False),
        (["docs/c.md"], False),
        (["uv.lock"], True),
        (["pyproject.toml"], True),
        (["tools/rules.py"], True),
        (["tools/checks/vocabulary.py"], True),
        (["src/catalyst_ai/app.py", "Makefile"], True),
    ],
)
def test_a_change_to_a_rule_config_lockfile_or_check_runs_every_file(
    paths: list[str], full: bool
) -> None:
    assert needs_full(paths) is full
    assert (scope_of(Path(), paths) is None) is full


def test_the_staged_set_is_what_the_commit_holds_and_a_deleted_file_is_not_in_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for variable in GIT_ENVIRONMENT:
        monkeypatch.delenv(variable, raising=False)
    assert git_output(tmp_path, "init", "-q") is not None
    changed, untouched = plant(tmp_path)
    assert staged(tmp_path) == []
    assert git_output(tmp_path, "add", "src") is not None
    assert staged(tmp_path) == ["src/catalyst_ai/changed.py", "src/catalyst_ai/untouched.py"]
    assert git_output(tmp_path, "rm", "-q", "--cached", str(untouched)) is not None
    assert staged(tmp_path) == ["src/catalyst_ai/changed.py"]
    del changed


def test_only_the_staged_python_files_are_formatted_and_linted_and_types_stay_whole() -> None:
    assert precommit.commands(["docs/c.md"]) == []
    runs = precommit.commands(["src/catalyst_ai/cli.py", "docs/b.md", "evals/x/g.py"])
    assert [run[2:4] for run in runs] == [["ruff", "format"], ["ruff", "check"], ["mypy", "src"]]
    assert runs[0][-1] == "src/catalyst_ai/cli.py"
    assert runs[2][-3:] == ["src", "tools", "tests"]
    assert precommit.commands(["uv.lock"])[0][-3:] == ["src", "tests", "tools"]


def test_a_file_staged_in_part_is_found_and_a_whole_one_is_not(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    for variable in GIT_ENVIRONMENT:
        monkeypatch.delenv(variable, raising=False)
    assert git_output(tmp_path, "init", "-q") is not None
    changed, untouched = plant(tmp_path)
    assert git_output(tmp_path, "add", "src") is not None
    paths = staged(tmp_path)
    assert partly_staged(tmp_path, paths) == []
    changed.write_text(LONG + "late = 1\n", encoding="utf-8")
    assert partly_staged(tmp_path, paths) == ["src/catalyst_ai/changed.py"]
    del untouched


def test_a_deleted_module_still_runs_the_type_check_that_finds_its_importers() -> None:
    assert precommit.commands([], ("src/catalyst_ai/capabilities/brief/facts.py",)) == [
        [*precommit.commands(["src/catalyst_ai/x.py"])[2]]
    ]
    assert precommit.commands([], ("docs/old.md",)) == []


def test_every_run_says_why_it_is_scoped_or_whole() -> None:
    assert reason([]) == "every file: nothing is staged"
    assert reason([], ("src/old.py",)) == "1 staged deletions and nothing else"
    assert (
        reason(["docs/a.md", "uv.lock"]) == "every file: uv.lock moves what every file is judged by"
    )
    assert reason(["docs/a.md", "src/catalyst_ai/cli.py"]) == "2 staged files"
