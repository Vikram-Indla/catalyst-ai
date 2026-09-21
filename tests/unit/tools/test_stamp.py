"""The run-once stamp: the tree hash sees every file, the check sees the tree, the image, the age."""

import json
from pathlib import Path

import pytest

from tools import stamp
from tools.checks.gitinfo import git_output

IMAGE = "python:3.12.14-slim"
DIGEST = "sha256:abc"
DAY_S = 24 * 60 * 60


REPO_ENV = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR", "GIT_OBJECT_DIRECTORY")


@pytest.fixture
def repo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A throwaway repository; the pipeline image points git at the real one, so unset that."""
    for name in REPO_ENV:
        monkeypatch.delenv(name, raising=False)
    assert git_output(tmp_path, "init", "-q", "-b", "main") is not None
    (tmp_path / ".gitignore").write_text("ignored.txt\n", encoding="utf-8")
    (tmp_path / "a.py").write_text("print(1)\n", encoding="utf-8")
    assert git_output(tmp_path, "add", ".") is not None
    identity = ("-c", "user.name=t", "-c", "user.email=t@example.invalid")
    assert git_output(tmp_path, *identity, "commit", "-q", "-m", "chore: seed") is not None
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(stamp, "image_digest", lambda _image: DIGEST)
    return tmp_path


def test_the_tree_hash_sees_edits_untracked_files_and_deletions_but_not_ignored_ones(
    repo: Path,
) -> None:
    clean = stamp.tree_hash()
    assert stamp.tree_hash() == clean
    (repo / "ignored.txt").write_text("x", encoding="utf-8")
    assert stamp.tree_hash() == clean
    (repo / "new.txt").write_text("x", encoding="utf-8")
    with_untracked = stamp.tree_hash()
    assert with_untracked != clean
    (repo / "new.txt").unlink()
    assert stamp.tree_hash() == clean
    (repo / "a.py").write_text("print(2)\n", encoding="utf-8")
    assert stamp.tree_hash() != clean
    (repo / "a.py").unlink()
    assert stamp.tree_hash() not in {clean, with_untracked}


def test_a_green_run_is_honoured_until_the_tree_the_image_or_the_day_moves(repo: Path) -> None:
    assert stamp.reason_to_run(IMAGE) is not None
    written = stamp.write(IMAGE)
    assert stamp.stamp_path().resolve() == (repo / ".git" / stamp.STAMP_NAME).resolve()
    assert json.loads(stamp.stamp_path().read_text(encoding="utf-8"))["tree"] == written["tree"]
    assert stamp.reason_to_run(IMAGE) is None
    assert stamp.reason_to_run("python:3.13-slim") == "the image is not the one the green run used"
    at = float(str(written["at"]))
    assert stamp.reason_to_run(IMAGE, now=at + DAY_S - 1) is None
    assert "old" in str(stamp.reason_to_run(IMAGE, now=at + DAY_S + 1))
    (repo / "a.py").write_text("print(3)\n", encoding="utf-8")
    assert stamp.reason_to_run(IMAGE) == "the tree changed since its last green run"
    stamp.stamp_path().write_text("{not json", encoding="utf-8")
    assert "no readable stamp" in str(stamp.reason_to_run(IMAGE))


def test_the_command_line_writes_checks_and_prints(
    repo: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert stamp.main(["check", "--image", IMAGE]) == 1
    assert stamp.main(["write", "--image", IMAGE]) == 0
    assert stamp.main(["check", "--image", IMAGE]) == 0
    assert stamp.main(["tree"]) == 0
    out = capsys.readouterr().out
    assert "no green run" in out
    assert "-- green" in out
    assert out.rstrip().endswith(stamp.tree_hash())
