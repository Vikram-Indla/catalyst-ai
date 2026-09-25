"""What a commit changed, and whether the change moves the ground every check stands on.

The commit-time checks read only the staged set: files added, copied, modified or renamed (a
deleted file has nothing left to check). A change to a shared configuration, a rule, the lockfile,
the hooks or a check's own code moves what every file is judged by, so it runs the whole set, as
does a commit with nothing staged. The full gate on the tip is unchanged either way.

The checks read files from disk, so a file staged in part (the working copy differs from what
the commit holds) is refused rather than judged on content the commit will not contain. A
deleted Python module still runs the type check, which finds every file that imported it.
"""

from pathlib import Path

from tools.checks.gitinfo import git_output

FULL = (
    "pyproject.toml",
    "uv.lock",
    "Makefile",
    "mypy.ini",
    ".importlinter",
    ".githooks/",
    "tools/rules.py",
    "tools/checks/",
    "tools/scope.py",
    "tools/precommit.py",
    "tools/affected.py",
    "tools/evals.py",
)


def staged(root: Path) -> list[str]:
    """Return the staged paths that still exist: added, copied, modified or renamed."""
    names = git_output(root, "diff", "--cached", "--name-only", "--diff-filter=ACMR") or ""
    return sorted(name for name in names.splitlines() if name)


def deleted(root: Path) -> list[str]:
    """Return the staged deletions."""
    names = git_output(root, "diff", "--cached", "--name-only", "--diff-filter=D") or ""
    return sorted(name for name in names.splitlines() if name)


def partly_staged(root: Path, paths: list[str]) -> list[str]:
    """Return the staged paths whose working copy still differs from what the commit holds."""
    unstaged = set((git_output(root, "diff", "--name-only") or "").splitlines())
    return [path for path in paths if path in unstaged]


def reason(paths: list[str], removed: tuple[str, ...] = ()) -> str:
    """Say why a run reads every file, or how many staged files it reads."""
    if not paths:
        empty = "every file: nothing is staged"
        return f"{len(removed)} staged deletions and nothing else" if removed else empty
    moved = [path for path in paths if path.startswith(FULL)]
    if moved:
        return f"every file: {moved[0]} moves what every file is judged by"
    return f"{len(paths)} staged files"


def needs_full(paths: list[str]) -> bool:
    """Whether the change moves the ground: nothing staged, or a shared rule or tool among it."""
    return not paths or any(path.startswith(FULL) for path in paths)


def scope_of(root: Path, paths: list[str]) -> frozenset[Path] | None:
    """Return the files the per-file checks may read, or None for the whole repository."""
    if needs_full(paths):
        return None
    return frozenset((root / path).resolve() for path in paths)
