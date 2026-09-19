"""RULE-003 §1: a change to the contract document carries a changelog entry."""

from pathlib import Path

from tools import rules
from tools.checks.gate import Violation
from tools.checks.gitinfo import changed_since_main


def check(changed: list[str]) -> list[Violation]:
    """Report a document change without a changelog change, given the changed files."""
    document = rules.API_DOCUMENT.as_posix()
    changelog = rules.CHANGELOG.as_posix()
    if document in changed and changelog not in changed:
        return [Violation(document, 1, f"changed without an entry in {changelog}")]
    return []


def run(root: Path) -> list[Violation]:
    """Compare the branch's changed files against main."""
    return check(changed_since_main(root))
