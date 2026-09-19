"""What the git-aware checks read: the files changed since main, and the commits since main."""

import subprocess
from dataclasses import dataclass
from pathlib import Path

MAIN = "main"
PORCELAIN_PREFIX = 3


@dataclass(frozen=True)
class Commit:
    """One commit and the files it touches."""

    sha: str
    subject: str
    files: tuple[str, ...]


def git_output(root: Path, *args: str) -> str | None:
    try:
        completed = subprocess.run(
            ["git", *args], cwd=root, capture_output=True, text=True, check=False, encoding="utf-8"
        )
    except OSError:
        return None
    return completed.stdout if completed.returncode == 0 else None


def has_main(root: Path) -> bool:
    """Whether a main branch exists to compare against."""
    return git_output(root, "rev-parse", "--verify", "--quiet", MAIN) is not None


def changed_since_main(root: Path) -> list[str]:
    """Files changed on this branch and in the working tree, relative to main."""
    if not has_main(root):
        return []
    committed = git_output(root, "diff", "--name-only", f"{MAIN}...HEAD") or ""
    working = git_output(root, "status", "--porcelain") or ""
    files = set(committed.split())
    for line in working.splitlines():
        if len(line) > PORCELAIN_PREFIX:
            files.add(line[PORCELAIN_PREFIX:].split(" -> ")[-1])
    return sorted(files)


def commits_since_main(root: Path) -> list[Commit]:
    """Return the commits on this branch that main does not have, with their files."""
    if not has_main(root):
        return []
    listing = git_output(root, "log", "--format=%H%x00%s", f"{MAIN}..HEAD") or ""
    commits = []
    for line in listing.splitlines():
        sha, _, subject = line.partition("\x00")
        files = (git_output(root, "show", "--name-only", "--format=", sha) or "").split()
        commits.append(Commit(sha=sha, subject=subject, files=tuple(files)))
    return commits
