"""The commit-time check: one scoped entry point for the pre-commit hook and a record's gate.

It reads the staged set (`tools/scope.py`) and fits in seconds: formatting and lint on the staged
Python files, the gate's per-file checks on the staged files, and a cross-file check on the whole
repository when a staged file is one it reads. A change that moves the ground, or a commit with
nothing staged, formats and lints every file and runs every cross-file check. The type check, the
tests and the evals run on the hosted runner after the push (`make verify-push`), and the eval
budgets, the drills and the storage suite in the nightly.
"""

import subprocess
import sys
from pathlib import Path

from tools.checks import gate
from tools.scope import deleted, needs_full, partly_staged, reason, staged

CODE_ROOTS = ("src/", "tests/", "tools/")
EXIT_FAIL = 1


def _targets(paths: list[str], full: bool) -> list[str]:
    if full:
        return [root.rstrip("/") for root in CODE_ROOTS]
    return [path for path in paths if path.endswith(".py") and path.startswith(CODE_ROOTS)]


def commands(paths: list[str], removed: tuple[str, ...] = ()) -> list[list[str]]:
    """Return the tool runs the change needs, in order; a deletion alone runs none."""
    targets = _targets(paths, needs_full(paths) and not removed)
    python = [sys.executable, "-m"]
    runs = [[*python, "ruff", "format", "--check", *targets], [*python, "ruff", "check", *targets]]
    return runs if targets else []


def _tools_and_gate_pass(paths: list[str], removed: tuple[str, ...]) -> bool:
    for command in commands(paths, removed):
        if subprocess.run(command, check=False).returncode != 0:
            return False
    return gate.main(["--fast", "--staged"]) == 0


def main(argv: list[str]) -> int:
    """Run the scoped checks for the staged set; stop at the first red step."""
    del argv
    root = Path.cwd()
    paths, removed = staged(root), tuple(deleted(root))
    print(f"precommit: {reason(paths, removed)}")
    split = partly_staged(root, paths)
    if split:
        print(f"precommit: staged in part, stage the whole file or set the rest aside: {split}")
    if split or not _tools_and_gate_pass(paths, removed):
        return EXIT_FAIL
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
