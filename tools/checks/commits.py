"""RULE-005 §2: generated artefacts are committed on their own, never with hand-written files."""

from pathlib import Path

from tools import rules
from tools.checks.gate import Violation
from tools.checks.gitinfo import Commit, commits_since_main


def is_generated(path: str) -> bool:
    """Whether a path is a generated artefact."""
    if path.startswith(rules.GENERATED_PATHS) or path in rules.GENERATED_PATHS:
        return True
    return (
        path.startswith(rules.LEDGERS.as_posix())
        and path.rsplit("/", 1)[-1] in rules.GENERATED_LEDGERS
    )


def check(commits: list[Commit]) -> list[Violation]:
    """Report every commit that mixes generated and hand-written files."""
    violations = []
    for commit in commits:
        generated = [f for f in commit.files if is_generated(f)]
        written = [f for f in commit.files if not is_generated(f)]
        if generated and written:
            message = f"commit {commit.sha[:10]} mixes generated {generated[0]} with {written[0]}"
            violations.append(Violation(".git", 1, message))
    return violations


def run(root: Path) -> list[Violation]:
    """Inspect the branch's commits since main."""
    return check(commits_since_main(root))
